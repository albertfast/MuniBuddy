from fastapi import APIRouter, HTTPException, Query
from app.services.schedule_service import SchedulerService

router = APIRouter()

scheduler_service = SchedulerService()

@router.get("/stop-schedule/{stop_id}")
def get_stop_schedule(stop_id: str, agency: str = Query("muni", description="Transit agency, e.g., 'muni' or 'bart'")):
    """
    Returns upcoming scheduled trips (inbound/outbound) for the given stop_id and agency from GTFS static data in PostgreSQL.
    """
    try:
        result = scheduler_service.get_schedule(stop_id=stop_id, agency=agency)
        if not result["inbound"] and not result["outbound"]:
            return {"message": f"No scheduled trips found for stop '{stop_id}' and agency '{agency}'", "data": result}
        return {"stop_id": stop_id, "agency": agency, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule fetch failed for stop '{stop_id}', agency '{agency}': {str(e)}")
