from fastapi import APIRouter, HTTPException
from app.core.singleton import scheduler_service  # updated from bus_service to scheduler_service

router = APIRouter()

@router.get("/stop-schedule/{stop_id}")
async def get_stop_schedule(stop_id: str):
    """
    Returns real-time schedule if available from 511 API,
    otherwise falls back to static GTFS schedule from PostgreSQL.
    """
    try:
        # Use scheduler_service for fetching real-time and fallback schedule
        return await scheduler_service.get_schedule(stop_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule fetch failed: {str(e)}")
