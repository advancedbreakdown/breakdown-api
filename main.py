from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base
import requests
from math import radians, sin, cos, sqrt, atan2

# -----------------------------
# DATABASE CONFIG
# -----------------------------
DATABASE_URL = "postgresql://postgres:breakdown2026@localhost:5432/breakdown_api"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ⭐ CREATE TABLES ON STARTUP ⭐
Base.metadata.create_all(bind=engine)

# -----------------------------
# DATABASE MODEL
# -----------------------------
class Garage(Base):
    __tablename__ = "garages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    phone = Column(String)
    email = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)

# -----------------------------
# PYDANTIC MODELS
# -----------------------------
class GarageCreate(BaseModel):
    name: str
    address: str
    phone: str | None = None
    email: str | None = None
    latitude: float | None = None
    longitude: float | None = None

class GarageOut(GarageCreate):
    id: int
    class Config:
        orm_mode = True

class BulkGarage(BaseModel):
    name: str
    address: str
    postcode: str
    phone: str | None = None
    notes: str | None = None

# -----------------------------
# FASTAPI APP
# -----------------------------
app = FastAPI()

# -----------------------------
# DB SESSION
# -----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------
# GEOCODING FUNCTION
# -----------------------------
def geocode_postcode(postcode: str):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={postcode}"
    response = requests.get(url, headers={"User-Agent": "breakdown-api"})
    data = response.json()
    if not data:
        return None, None
    return float(data[0]["lat"]), float(data[0]["lon"])

# -----------------------------
# HAVERSINE DISTANCE
# -----------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# -----------------------------
# ENDPOINTS
# -----------------------------
@app.get("/garages", response_model=List[GarageOut])
def list_garages(db=Depends(get_db)):
    return db.query(Garage).all()

@app.post("/garages", response_model=GarageOut)
def create_garage(garage: GarageCreate, db=Depends(get_db)):
    db_garage = Garage(**garage.dict())
    db.add(db_garage)
    db.commit()
    db.refresh(db_garage)
    return db_garage

# -----------------------------
# BULK UPLOAD WITH GEOCODING
# -----------------------------
@app.post("/garages/bulk_upload")
def bulk_upload_garages(garages: List[BulkGarage], db=Depends(get_db)):
    saved = 0
    for g in garages:
        lat, lon = geocode_postcode(g.postcode)

        db_garage = Garage(
            name=g.name,
            address=g.address,
            phone=g.phone,
            email=None,
            latitude=lat,
            longitude=lon
        )

        db.add(db_garage)
        saved += 1

    db.commit()
    return {"message": f"{saved} garages uploaded successfully"}

# -----------------------------
# FIND NEAREST GARAGES
# -----------------------------
@app.get("/garages/nearest")
def nearest_garages(postcode: str, db=Depends(get_db)):
    lat, lon = geocode_postcode(postcode)
    if lat is None:
        raise HTTPException(status_code=400, detail="Invalid postcode")

    garages = db.query(Garage).all()

    results = []
    for g in garages:
        if g.latitude and g.longitude:
            distance = haversine(lat, lon, g.latitude, g.longitude)
            results.append({
                "name": g.name,
                "address": g.address,
                "phone": g.phone,
                "distance_km": round(distance, 2)
            })

    results.sort(key=lambda x: x["distance_km"])
    return results
