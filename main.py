from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql://postgres:breakdown2026@localhost:5432/breakdown_api"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Garage(Base):
    __tablename__ = "garages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    phone = Column(String)
    email = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)

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

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from fastapi import Depends

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