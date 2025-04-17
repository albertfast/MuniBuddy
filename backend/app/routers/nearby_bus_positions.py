from fastapi import APIRouter, Query, HTTPException
import httpx
from app.config import settings

router = APIRouter()

@router.get("/bus-positions/by-stop")
def get_bus_positions_by_stop(
    stopCode: str = Query(..., description="Stop code from GTFS (e.g., 14212)"),
    agency: str = Query("SF", description="Transit agency code (e.g., SF, SFMTA, muni, BA, bart)")
):
    """
    Returns raw real-time data from 511.org for the given stopCode and agency.
    Accepts aliases like muni, SFMTA for SF; bart or BA for BART.
    """
    normalized_agency = {
        "SF": "SF",
        "SFMTA": "SF",
        "muni": "SF",
        "BA": "BA",
        "bart": "BA"
    }.get(agency.lower(), agency)

    try:
        url = f"{settings.TRANSIT_511_BASE_URL}/StopMonitoring"
        params = {
            "api_key": settings.API_KEY,
            "agency": normalized_agency,
            "stopCode": stopCode,
            "format": "json"
        }

        response = httpx.get(url, params=params)
        response.raise_for_status()

        return response.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch 511 data: {e}")
