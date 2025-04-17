from fastapi import APIRouter, HTTPException, Query
from app.services.scheduler_service import SchedulerService

router = APIRouter()
schedule_service = SchedulerService()

@router.get("/stop-schedule/{stop_id}")
def get_stop_schedule(stop_id: str, agency: str = Query("muni", enum=["muni", "bart"])):
    """
    Returns upcoming scheduled stops from GTFS data in DB.
    """
    try:
        return schedule_service.get_schedule(stop_id, agency=agency)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule fetch failed: {str(e)}")
