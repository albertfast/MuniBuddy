from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import bus_service
from typing import Optional

router = APIRouter()

@router.get("/bus/nearby-stops")
def get_nearby_bus_stops(
    lat: float = Query(..., description="Latitude of the user"),
    lon: float = Query(..., description="Longitude of the user"),
    radius: float = Query(0.15, description="Search radius in miles"),
    agency: Optional[str] = Query(None, description="Transit agency (e.g., muni or bart)")
):
    try:
        return bus_service.get_nearby_stops(lat, lon, radius, agency=agency)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby bus stops: {e}")


@router.get("/bus/stop-arrivals/{stop_id}")
async def get_bus_stop_arrivals(
    stop_id: str,
    lat: Optional[float] = Query(None, description="User's latitude (optional)"),
    lon: Optional[float] = Query(None, description="User's longitude (optional)"),
    agency: Optional[str] = Query(None)
):
    try:
        return await bus_service.get_stop_predictions(stop_id, lat, lon)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bus arrivals: {e}")

