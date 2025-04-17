from fastapi import APIRouter, Query, HTTPException
from app.core.singleton import bart_service

router = APIRouter()

@router.get("/bart/nearby-stops")
def get_nearby_bart_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(0.15)
):
    """
    Returns nearby BART stops given a latitude and longitude.
    """
    try:
        return bart_service.get_nearby_stops(lat, lon, radius)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby BART stops: {e}")

@router.get("/bart/stop-arrivals/{stop_id}")
async def get_bart_stop_arrivals(
    stop_id: str,
    lat: float = Query(None),
    lon: float = Query(None),
    radius: float = Query(0.15)
):
    """
    Returns real-time arrivals (or fallback schedule) for a specific BART stop.
    """
    try:
        return await bart_service.get_real_time_arrivals(stop_id, lat, lon, radius)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch arrivals: {e}")

@router.get("/bart/route-stops/{route_id}")
def get_bart_route_stops(
    route_id: str,
    direction_id: int = 0
):
    """
    Returns list of stops for a given BART route and direction.
    """
    try:
        return bart_service.get_route_stops(route_id, direction_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch route stops: {e}")
