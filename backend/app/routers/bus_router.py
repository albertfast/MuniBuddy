from fastapi import APIRouter, HTTPException
from app.core.singleton import bus_service
from fastapi import Query

router = APIRouter()

@router.get("/bus/nearby-stops")
def get_nearby_bus_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(0.15),
    agency: str = Query("muni")
):
    """
    Returns nearby MUNI stops given a latitude and longitude.
    """
    try:
        return bus_service.get_nearby_stops(lat, lon, radius, agency=agency)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby bus stops: {e}")


@router.get("/bus/stop-arrivals/{stop_id}")
async def get_bus_stop_arrivals(
    stop_id: str,
    lat: float = Query(None),
    lon: float = Query(None),
    radius: float = Query(0.15),
    agency: str = Query("muni")
):
    try:
        return await bus_service.get_stop_predictions(stop_id, lat, lon, radius, agency)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bus arrivals: {e}")

@router.get("/bus/nearby-stops")
def get_nearby_bus_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(0.15)
):
    try:
        return bus_service.get_nearby_stops(lat, lon, radius, agency="muni")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby bus stops: {e}")

