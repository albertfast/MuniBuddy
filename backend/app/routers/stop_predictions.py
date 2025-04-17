from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import schedule_service, bart_service
from app.services.realtime_service import fetch_real_time_stop_data
from app.services.gtfs_service import GTFSService
from app.config import settings
from app.services.debug_logger import log_debug

router = APIRouter()

def detect_agency_by_stop(stop_id: str, stop_code: str | None = None) -> str:
    """
    Search GTFS DB tables using GTFSService to determine which agency has the stop_id or stop_code.
    """
    for agency in settings.GTFS_AGENCIES:
        gtfs = GTFSService(agency)
        stops_df = gtfs.get_stops()
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
    agency: str = Query("muni"),
    stop_code: str = Query(None)
):
    try:
        # Step 1: Detect agency dynamically from database
        agency = settings.normalize_agency(agency) if agency else settings.normalize_agency(detect_agency_by_stop(stop_id, stop_code))

        # Step 2: BART handling
        if agency == "bart":
            detailed = await bart_service.get_bart_stop_details(stop_id)
            realtime = await bart_service.get_real_time_arrivals(stop_id, lat, lon)

            if not realtime.get("inbound") and not realtime.get("outbound"):
                fallback = schedule_service.get_schedule(stop_id, agency="bart")
                detailed["realtime"] = fallback
            else:
                # Ensure vehicle key always exists for consistency
                for entry in realtime.get("inbound", []) + realtime.get("outbound", []):
                    entry.setdefault("vehicle", {"lat": "", "lon": ""})
                detailed["realtime"] = realtime

            return detailed

        # Step 3: MUNI handling
        realtime = await fetch_real_time_stop_data(stop_id, agency="muni")
        if not realtime.get("inbound") and not realtime.get("outbound"):
            return schedule_service.get_schedule(stop_id, agency="muni")

        # Ensure vehicle field is present
        for entry in realtime.get("inbound", []) + realtime.get("outbound", []):
            entry.setdefault("vehicle", {"lat": "", "lon": ""})

        return realtime

    except Exception as e:
        log_debug(f"[STOP PREDICTIONS] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction fetch failed: {str(e)}")
