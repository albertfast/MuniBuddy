from fastapi import APIRouter, Query
from app.core.singleton import bus_service

router = APIRouter()

@router.get("/nearby-stops")
async def get_nearby_stops(lat: float = Query(...), lon: float = Query(...), radius_miles: float = 0.2):
    return await bus_service.find_nearby_stops(lat, lon, radius_miles)
