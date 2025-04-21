from typing import Optional
from app.core.singleton import bus_service 
from fastapi import APIRouter, Query, HTTPException
from app.config import settings
from app.services.debug_logger import log_debug
import httpx

router = APIRouter()

def normalize_agency(agency: str) -> str:
    agency = agency.lower()
    if agency in ["sf", "muni", "sfmta"]:
        return "SF"
    elif agency in ["ba", "bart"]:
        return "BA"
    return agency.upper()

@router.get("/bus-positions/nearby")
def get_bus_positions_nearby(
    lat: float = Query(..., description="User's latitude"),
    lon: float = Query(..., description="User's longitude"),
    radius: float = Query(0.15, description="Search radius in miles"),
    agency: str = Query("muni", description="Transit agency (e.g., muni, bart)")
):
    """
    Returns real-time bus predictions for nearby stops, with GTFS fallback.
    Aggregated into a single response to avoid 511 API overuse.
    """
    try:
        log_debug(f"[API] Fetching nearby bus positions lat={lat}, lon={lon}, agency={agency}, radius={radius}")
        return bus_service.get_nearby_buses(lat, lon, radius, agency)
    except Exception as e:
        log_debug(f"[API] ❌ Failed to fetch nearby bus positions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby bus data: {e}")

@router.get("/bus-positions/by-stop")
async def get_bus_positions_by_stop(
    stopCode: str = Query(..., description="GTFS stop_code or stop_id"),
    agency: str = Query("muni", description="Agency name (e.g., muni, SFMTA, bart)")
):
    """
    Fetch raw SIRI StopMonitoring data for a single stopCode & agency.
    Returns 511 SIRI-compliant JSON.
    """
    try:
        norm_agency = normalize_agency(agency)
        log_debug(f"[API] Fetching SIRI StopMonitoring for stopCode={stopCode}, agency={norm_agency}")

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
