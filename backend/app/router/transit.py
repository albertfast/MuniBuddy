from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.bus_service import BusService
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/api/nearby-stops")
async def get_nearby_stops(
    lat: float = Query(..., description="Latitude of the location"),
    lon: float = Query(..., description="Longitude of the location"),
    radius_miles: float = Query(0.5, description="Search radius in miles"),
    db: Session = Depends(get_db)
):
    """Get nearby bus stops within the specified radius."""
    try:
        bus_service = BusService(db)
        return await bus_service.get_nearby_stops(lat, lon, radius_miles)
    except Exception as e:
        logger.error(f"Error getting nearby stops: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/stop-schedule/{stop_id}")
async def get_stop_schedule(stop_id: str, db: Session = Depends(get_db)):
    """Get real-time bus schedule for a specific stop."""
    try:
        bus_service = BusService(db)
        return await bus_service.get_stop_schedule(stop_id)
    except Exception as e:
        logger.error(f"Error getting stop schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 