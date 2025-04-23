from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import httpx

from app.core.singleton import bart_service
from app.config import settings
from app.services.debug_logger import log_debug
from app.routers.nearby_stops import get_combined_nearby_stops

router = APIRouter(prefix="/bart-positions", tags=["BART Positions"])

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
        norm_agency = settings.normalize_agency(agency, to_511=True)
        log_debug(f"[API] Fetching SIRI StopMonitoring for stopCode={stopCode}, agency={norm_agency}")

        # First verify that the stopCode belongs to BART
        nearby_stops = get_combined_nearby_stops(lat=37.0, lon=-122.0, radius=50.0)  # Dummy coords for full list
        bart_stops = [s for s in nearby_stops if s.get("agency") == "bart"]
        if stopCode not in {s.get("stop_code") for s in bart_stops}:
            raise HTTPException(status_code=404, detail=f"Stop {stopCode} not found for BART")

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