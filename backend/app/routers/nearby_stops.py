from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import bus_service

router = APIRouter()

@router.get("/nearby-stops")
def get_nearby_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = 0.15,
    agency: str = Query("muni")
):
    try:
        return bus_service.get_nearby_stops(lat=lat, lon=lon, radius=radius, agency=agency)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby stops: {e}")