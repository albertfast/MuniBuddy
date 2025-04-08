from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import bus_service

router = APIRouter()

@router.get("/nearby-stops")
async def get_nearby_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_miles: float = Query(0.15)
):
    """
    Return nearby transit stops within a radius
    """
    try:
        return await bus_service.get_nearby_buses(lat, lon, radius_miles)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))