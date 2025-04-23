from fastapi import APIRouter, Query, HTTPException
from app.core.singleton import bart_service
from app.config import settings
from app.services.debug_logger import log_debug
from app.services.stop_helper import load_stops
from app.integrations.siri_api import fetch_siri_data_multi
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

@router.get("/nearby-stops")
async def get_nearby_bart_stops(
    lat: float = Query(..., description="Latitude of the user"),
    lon: float = Query(..., description="Longitude of the user"),
    radius: float = Query(0.15, description="Search radius in miles"),
    agency: Optional[str] = Query(None, description="Transit agency (e.g., muni or bart)")
):
    """
    Returns nearby stops from one or more agencies (Muni, BART) around a given location.
    If no agency is specified, returns stops from all GTFS agencies.
    """
    try:
        return bart_service.get_nearby_stops(lat, lon, radius, agency=agency)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby bus stops: {e}")
