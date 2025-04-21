from fastapi import APIRouter, Query, HTTPException
from app.services.debug_logger import log_debug
from app.integrations.siri_api import fetch_siri_data
from typing import Optional

router = APIRouter()

from app.config import settings


@router.get("/bus-positions/by-stop/{stop_code}")
async def get_bus_positions_by_location(
    agency = settings.normalize_agency(agency)
    stop_code: str,
    lat: float = Query(..., description="User's latitude"),
    lon: float = Query(..., description="User's longitude"),
    radius: float = Query(0.15, description="Search radius in miles"),
    agency: str = Query({agency}, description="Transit agency (e.g., muni, bart)")
):
    """
    Fetch real-time bus positions near a location using GTFS stops + 511 SIRI API.
    Returns structured inbound/outbound vehicle data.
    """
    try:
        log_debug(f"[API] /bus-positions/by-stop lat={lat}, lon={lon}, agency={agency}, radius={radius}")
        siri_result = await fetch_siri_data(lat, lon, agency, radius)

        if not siri_result["inbound"] and not siri_result["outbound"]:
            log_debug("[API] ⚠ No inbound or outbound data found from SIRI.")
        return siri_result

    except Exception as e:
        log_debug(f"[API] ❌ Failed to fetch SIRI data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch bus positions: {e}")