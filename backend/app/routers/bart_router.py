from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from app.config import settings
from app.services.debug_logger import log_debug
from app.services.stop_helper import load_stops
import httpx

router = APIRouter(prefix="/bart-positions", tags=["BART Positions"])

def normalize_agency(agency: str) -> str:
    agency = agency.lower()
    if agency in ["sf", "muni", "sfmta"]:
        return "SF"
    elif agency in ["ba", "bart"]:
        return "BA"
    return agency.upper()

@router.get("/by-stop")
async def get_parsed_bart_by_stop(
    stopCode: str = Query(..., description="GTFS stop_code or stop_id"),
    agency: str = Query("bart", description="Agency name (e.g., muni, SFMTA, bart)")
):
    """
    Fetch raw SIRI StopMonitoring data for a single stopCode & agency.
    Returns 511 SIRI-compliant JSON.
    """
    try:
        norm_agency = normalize_agency(agency)
        log_debug(f"[API] Fetching SIRI StopMonitoring for stopCode={stopCode}, agency={norm_agency}")

        # Filter from preloaded GTFS stops to verify the stopCode exists and belongs to BART
        all_stops = load_stops("bart")
        matching_stop = next((stop for stop in all_stops if stop["stop_code"] == stopCode), None)
        if not matching_stop:
            raise HTTPException(status_code=404, detail=f"StopCode '{stopCode}' not found for BART")

        url = f"{settings.TRANSIT_511_BASE_URL}/StopMonitoring"
        params = {
            "api_key": settings.API_KEY,
            "agency": norm_agency,
            "stopCode": stopCode,
            "format": "json"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    except Exception as e:
        log_debug(f"[API] ❌ SIRI fetch failed for stopCode={stopCode}, agency={agency}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch 511 SIRI data: {e}")