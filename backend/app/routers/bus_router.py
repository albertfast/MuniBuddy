from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.core.singleton import bus_service
from app.config import settings

router = APIRouter()

@router.get("/bus/nearby-stops")
def get_nearby_bus_stops(
    lat: float = Query(..., description="Latitude of the user"),
    lon: float = Query(..., description="Longitude of the user"),
    radius: float = Query(0.15, description="Search radius in miles"),
    agency: Optional[str] = Query(None, description="Transit agency (e.g., muni or bart)")
):
    """
    Returns nearby stops from one or more agencies (Muni, BART) around a given location.
    If no agency is specified, returns stops from all GTFS agencies.
    """
    try:
        return bus_service.get_nearby_stops(lat, lon, radius, agency=agency)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby bus stops: {e}")

