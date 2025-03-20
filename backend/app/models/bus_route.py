from sqlalchemy import Column, String, Integer, Float
from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends
from app.db.database import Base, get_db
from app.config import settings

class BusRoute(Base):
    __tablename__ = "bus_routes"
    
    id = Column(Integer, primary_key=True)
    route_id = Column(String, unique=True)  # the route_id data coming from GTFS
    line_ref = Column(String)  # The LineRef will be match with API 
    agency_id = Column(String)
    route_name = Column(String)
    direction = Column(String)
    origin = Column(String)
    destination = Column(String)
    
    def __repr__(self):
        return f"<BusRoute {self.route_name} ({self.agency_id})>"

print("[DEBUG] BusRoute model initialized")