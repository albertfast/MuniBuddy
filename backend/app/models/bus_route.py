from sqlalchemy import Column, String, Integer, Float
from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends
from dotenv import load_dotenv

from app.config import settings
API_KEY = settings.API_KEY
REDIS_HOST = settings.REDIS_HOST
REDIS_PORT = settings.REDIS_PORT
from app.database import Base, get_db
import os
load_dotenv()
# 🌍 Read environment variables
API_KEY = os.getenv("API_KEY")
AGENCY_ID = os.getenv("AGENCY_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI()


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