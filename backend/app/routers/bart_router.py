from fastapi import APIRouter, Query, HTTPException, Request
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
    agency: str = Query(default="bart", description="Agency name (e.g., muni, bart)"),
    request: Request = None
):
    try:
        norm_agency = settings.normalize_agency(agency, to_511=True)

        # Internal request to the /nearby-stops endpoint
        client = httpx.AsyncClient(base_url=str(request.base_url))
        nearby_response = await client.get("/api/v1/nearby-stops?lat=37.0&lon=-122.0&radius=50")
        nearby_response.raise_for_status()
        nearby_stops = nearby_response.json()

        # Check if stopCode belongs to BART
        bart_stops = [s for s in nearby_stops if s.get("agency") == "bart"]
        if stopCode not in {s.get("stop_code") for s in bart_stops}:
            raise HTTPException(status_code=404, detail=f"Stop {stopCode} not found in BART stops")

        # Fetch real-time data from 511 API
        url = f"{settings.TRANSIT_511_BASE_URL}/StopMonitoring"
        params = {
            "api_key": settings.API_KEY,
            "agency": norm_agency,
            "stopCode": stopCode,
            "format": "json"
        }

        async with httpx.AsyncClient(timeout=10.0) as external_client:
            siri_response = await external_client.get(url, params=params)
            siri_response.raise_for_status()
            return siri_response.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch 511 SIRI data: {e}")