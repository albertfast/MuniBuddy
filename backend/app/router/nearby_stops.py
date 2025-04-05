import os
import sys
# For when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging

from app.db.database import get_db, SessionLocal
from app.services.bus_service import BusService

# Create a database session for global service
db = SessionLocal()
bus_service = BusService(db=db)  # Fix: Pass the db session

# Initialize router
router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/nearby-stops")
async def get_nearby_stops(
    lat: float = Query(..., description="Latitude of the search point"),
    lon: float = Query(..., description="Longitude of the search point"),
    radius: float = Query(0.15, description="Search radius in miles"),
    limit: int = Query(10, description="Maximum number of stops to return"),
    db: Session = Depends(get_db)  # Use dependency injection here
):
    """Find transit stops near a given location"""
    try:
        # Use the global bus_service instance
        stops = await bus_service.find_nearby_stops(lat, lon, radius, limit)
        return {"stops": stops, "count": len(stops)}
    except Exception as e:
        logger.exception(f"Error finding nearby stops: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving nearby stops: {str(e)}")