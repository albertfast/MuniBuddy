# app/routers/nearby_stops.py

from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import bus_service

router = APIRouter()

@router.get("/nearby-stops")
async def get_nearby_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_miles: float = 0.15
):
    """
    Get nearby transit stops using BusService.
    """
    try:
        return await bus_service.get_nearby_buses(lat=lat, lon=lon, radius_miles=radius_miles)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby stops: {e}")
