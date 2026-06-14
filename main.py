from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import requests
import math

# -----------------------------
# DATABASE (PostgreSQL)
# -----------------------------
DATABASE_URL = "postgresql://breakdown_new_user:yinDOUdsP4QvmLfQlfhxoNuuhkm90zHD@dpg-d8neunjeo5us73esa4b0-a/breakdown_new"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# -----------------------------
# MODELS
# -----------------------------
class Garage(Base):
    __tablename__ = "garages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    postcode = Column(String, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)


Base.metadata.create_all(bind=engine)


# -----------------------------
# SCHEMAS
# -----------------------------
class GarageCreate(BaseModel):
    name: str
    postcode: str
    latitude: float
    longitude: float
    phone: str | None = None
    email: str | None = None


class GarageOut(BaseModel):
    id: int
    name: str
    postcode: str
    latitude: float
    longitude: float
    phone: str | None = None
    email: str | None = None

    class Config:
        from_attributes = True


# Bulk upload schema
class BulkGarageCreate(BaseModel):
    garages: list[GarageCreate]


# -----------------------------
# FASTAPI APP
# -----------------------------
app = FastAPI()

# -----------------------------
# CORS FIX (REQUIRED FOR GITHUB PAGES)
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://advancedbreakdown.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# DB DEPENDENCY
# -----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# HELPERS
# -----------------------------
def geocode_postcode(postcode: str):
    postcode = postcode.replace(" ", "").upper()

    url = f"https://api.postcodes.io/postcodes/{postcode}"
    response = requests.get(url).json()

    if response.get("status") != 200:
        return None

    result = response["result"]
    return result["latitude"], result["longitude"]


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lat2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# -----------------------------
# ROUTES
# -----------------------------

# Single garage upload
@app.post("/garages/", response_model=GarageOut)
def create_garage(garage: GarageCreate, db: Session = Depends(get_db)):
    db_garage = Garage(
        name=garage.name,
        postcode=garage.postcode,
        latitude=garage.latitude,
        longitude=garage.longitude,
        phone=garage.phone,
        email=garage.email,
    )
    db.add(db_garage)
    db.commit()
    db.refresh(db_garage)
    return db_garage


# List all garages
@app.get("/garages/", response_model=list[GarageOut])
def list_garages(db: Session = Depends(get_db)):
    return db.query(Garage).all()


# Bulk upload garages
@app.post("/garages/bulk")
def bulk_create_garages(data: BulkGarageCreate, db: Session = Depends(get_db)):
    created = []
    for g in data.garages:
        garage = Garage(
            name=g.name,
            postcode=g.postcode,
            latitude=g.latitude,
            longitude=g.longitude,
            phone=g.phone,
            email=g.email,
        )
        db.add(garage)
        created.append(garage)

    db.commit()
    return {"added": len(created)}


# Delete a garage
@app.delete("/garages/{garage_id}")
def delete_garage(garage_id: int, db: Session = Depends(get_db)):
    garage = db.query(Garage).filter(Garage.id == garage_id).first()
    if not garage:
        raise HTTPException(status_code=404, detail="Garage not found")

    db.delete(garage)
    db.commit()
    return {"message": "Garage deleted"}


# Update a garage
@app.put("/garages/{garage_id}", response_model=GarageOut)
def update_garage(garage_id: int, data: GarageCreate, db: Session = Depends(get_db)):
    garage = db.query(Garage).filter(Garage.id == garage_id).first()
    if not garage:
        raise HTTPException(status_code=404, detail="Garage not found")

    garage.name = data.name
    garage.postcode = data.postcode
    garage.latitude = data.latitude
    garage.longitude = data.longitude
    garage.phone = data.phone
    garage.email = data.email

    db.commit()
    db.refresh(garage)
    return garage


# Nearest garages
@app.get("/garages/nearest")
def nearest_garages(postcode: str, db: Session = Depends(get_db)):
    coords = geocode_postcode(postcode)
    if not coords:
        raise HTTPException(status_code=400, detail="Invalid postcode")

    user_lat, user_lon = coords
    garages = db.query(Garage).all()

    if not garages:
        raise HTTPException(status_code=404, detail="No garages found")

    results = []

    for g in garages:
        dist = haversine(user_lat, user_lon, g.latitude, g.longitude)
        results.append({
            "id": g.id,
            "name": g.name,
            "postcode": g.postcode,
            "latitude": g.latitude,
            "longitude": g.longitude,
            "phone": g.phone,
            "email": g.email,
            "distance_km": round(dist, 2)
        })

    results.sort(key=lambda x: x["distance_km"])
    return results

