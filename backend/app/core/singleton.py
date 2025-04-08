# app/core/singleton.py
from app.db.database import SessionLocal
from app.services.bus_service import BusService

db = SessionLocal()
bus_service = BusService(db=db)