from fastapi import APIRouter, HTTPException
from app.core.singleton import schedule_service

router = APIRouter()

@router.get("/stop-schedule/{stop_id}")
def get_stop_schedule(stop_id: str):
    """
    Returns static GTFS schedule from PostgreSQL.
    """
    try:
        return schedule_service.get_schedule(stop_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule fetch failed: {str(e)}")
