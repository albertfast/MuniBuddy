from fastapi import APIRouter, HTTPException
from app.services.schedule_service import get_static_schedule
from app.config import settings

router = APIRouter()

@router.get("/stop-schedule/{stop_id}")
async def get_stop_schedule(stop_id: str):
    """
    Returns static GTFS schedule for a stop using provided GTFS data.
    """
    try:
        gtfs_data = settings.get_gtfs_data("muni")
        return get_static_schedule(stop_id, gtfs_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule fetch failed: {str(e)}")
