from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import bus_service, scheduler_service, bart_service
from app.services.realtime_service import fetch_real_time_stop_data
from app.services.debug_logger import log_debug
from app.integrations.siri_api import fetch_siri_data

router = APIRouter()

def normalize_agency(agency_raw: str) -> str:
    """
    Normalize input agency strings to match internal codes.
    Examples: "sf", "SFMTA", "muni" -> "muni"; "BA", "bart" -> "bart"
    """
    agency_raw = agency_raw.lower()
    if agency_raw in ["sf", "sfmta", "muni"]:
        return "muni"
    elif agency_raw in ["ba", "bart"]:
        return "bart"
    return agency_raw

@router.get("/stop-predictions/{stop_id}")
async def get_stop_predictions(
    stop_id: str,
    lat: float = Query(None, description="Latitude (optional, for location-aware filtering)"),
    lon: float = Query(None, description="Longitude (optional, for location-aware filtering)"),
    agency: str = Query("muni", description="Transit agency: muni or bart"),
    detailed: bool = Query(False, description="If true, return detailed station info (BART only)")
):
    """
    Fetches real-time arrival predictions for the given stop.
    Automatically supports both MUNI and BART, with optional detailed output for BART.
    """
    try:
        agency = normalize_agency(agency)

        if agency == "bart":
            if detailed:
                return await bart_service.get_bart_stop_details(stop_id)
            return await bart_service.get_real_time_arrivals(stop_id, lat, lon)

        # Default: MUNI
        return await fetch_real_time_stop_data(stop_id, agency=agency)

    except Exception as e:
        log_debug(f"[STOP PREDICTIONS] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Real-time prediction failed: {str(e)}")

from fastapi.responses import JSONResponse
from fastapi import APIRouter, HTTPException
from app.core.singleton import bart_service
from app.services.debug_logger import log_debug

router = APIRouter()

@router.get("/debug/bart-raw/{stop_code}")
async def debug_bart_raw(stop_code: str):
    """
    Debug endpoint to fetch raw BART data from 511 SIRI API.
    Useful for verifying agency communication and stop code resolution.
    """
    try:
        raw = await bart_service.get_bart_511_raw_data(stop_code)

        if not raw or "ServiceDelivery" not in raw:
            log_debug(f"[DEBUG BART RAW] Empty or invalid response for stop: {stop_code}")
            return JSONResponse(
                status_code=204,
                content={"message": f"No content received for stop code: {stop_code}"}
            )

        return JSONResponse(
            status_code=200,
            content={
                "stop_code": stop_code,
                "received_at": datetime.utcnow().isoformat(),
                "summary": {
                    "inbound_count": len(raw.get("ServiceDelivery", {}).get("StopMonitoringDelivery", {}).get("MonitoredStopVisit", [])),
                },
                "raw": raw
            }
        )

    except Exception as e:
        log_debug(f"[DEBUG BART RAW] ❌ Failed to fetch raw data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch BART raw data: {str(e)}")

