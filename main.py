from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import requests
import math

# -----------------------------
# DATABASE (SQLite)
# -----------------------------
DATABASE_URL = "sqlite:///./breakdown.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

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
        orm_mode = True


# -----------------------------
# FASTAPI APP
# -----------------------------
app = FastAPI()


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
    url = f"https://api.postcodes.io/postcodes/{postcode}"
    response = requests.get(url).json()

    if response.get("status") != 200:
        return None

    result = response["result"]
    return result["latitude"], result["longitude"]


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
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


@app.get("/garages/", response_model=list[GarageOut])
def list_garages(db: Session = Depends(get_db)):
    return db.query(Garage).all()


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

    # Sort by distance
    results.sort(key=lambda x: x["distance_km"])

    # Return ALL garages sorted by distance
    return results
