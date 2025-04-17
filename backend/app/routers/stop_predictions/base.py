from fastapi import APIRouter, HTTPException, Query
from app.config import settings
from app.routers.stop_predictions import muni, bart
from app.services.gtfs_service import GTFSService
from app.services.debug_logger import log_debug

router = APIRouter()

def detect_agency_by_stop(stop_id: str, stop_code: str | None = None) -> str:
    for agency in settings.GTFS_AGENCIES:
        stops_df = GTFSService(agency).get_stops()
        found = stops_df[
            (stops_df["stop_id"] == stop_id) |
            (stops_df["stop_code"] == stop_id) |
            (stop_code is not None and stops_df["stop_code"] == stop_code)
        ]
        if not found.empty:
            return agency
    return "muni"

@router.get("/stop-predictions/{stop_id}")
async def get_stop_predictions(
    stop_id: str,
    lat: float = Query(None),
    lon: float = Query(None),
    agency: str = Query(None),
    stop_code: str = Query(None)
):
    try:
        normalized = settings.normalize_agency(agency or detect_agency_by_stop(stop_id, stop_code))
        
        if normalized == "bart":
            return await bart.get_bart_predictions(stop_id, lat, lon)

        return await muni.get_muni_predictions(stop_id)
        log_debug(f"[STOP_PREDICTIONS] {stop_id} resolved as {agency}")

    except Exception as e:
        log_debug(f"[STOP PREDICTIONS] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction fetch failed: {str(e)}")
        

