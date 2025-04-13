from fastapi import APIRouter, Query, HTTPException
from app.services.bart_service import BartService

router = APIRouter()
bart_service = BartService()

@router.get("/bart/nearby-stops")
def get_nearby_bart_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(0.15)
):
    try:
        return bart_service.get_nearby_stops(lat, lon, radius)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bart/stop-arrivals/{stop_id}")
async def get_bart_stop_arrivals(stop_id: str):
    try:
        return await bart_service.get_real_time_arrivals(stop_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bart/route-stops/{route_id}")
def get_bart_route_stops(route_id: str, direction_id: int = 0):
    try:
        return bart_service.get_route_stops(route_id, direction_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
