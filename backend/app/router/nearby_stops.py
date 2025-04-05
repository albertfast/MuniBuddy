import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db, SessionLocal
from app.services.bus_service import BusService

router = APIRouter()
db = SessionLocal()
bus_service = BusService(db=db)

@router.get("/api/nearby-stops")
async def get_nearby_stops(
    lat: float,
    lon: float,
    radius_miles: float = 0.15,
    db: Session = Depends(get_db)
):
    """
    Get nearby transit stops within the specified radius
    """
    try:
        nearby_stops = await bus_service.get_nearby_buses(lat, lon, radius_miles)
        return nearby_stops
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 