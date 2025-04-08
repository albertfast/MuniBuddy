# app/router/stop_schedule.py
from fastapi import APIRouter, HTTPException
from services.bus_service import bus_service

router = APIRouter()

@router.get("/stop-schedule/{stop_id}")
async def get_stop_schedule(stop_id: str):
    """
    Returns real-time schedule if available from 511 API,
    otherwise falls back to static GTFS schedule from PostgreSQL.
    """
    try:
        real_time_data = await bus_service.fetch_real_time_stop_data(stop_id)

        if real_time_data and (real_time_data.get("inbound") or real_time_data.get("outbound")):
            return real_time_data

        # Fallback to GTFS static schedule
        return await bus_service.get_stop_schedule(stop_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule fetch failed: {str(e)}")