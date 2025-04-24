from fastapi import APIRouter, Query, HTTPException
from app.config import settings
from app.services.stop_helper import load_stops
from app.services.bart_service import fetch_vehicle_locations_by_refs
import httpx

router = APIRouter(prefix="/bart-positions", tags=["BART Positions"])

@router.get("/by-stop")
async def get_parsed_bart_by_stop(
    stopCode: str = Query(...),
    agency: str = Query(default="bart")
):
    try:
        norm_agency = settings.normalize_agency(agency, to_511=True)

        bart_stops = load_stops("bart")
        valid_stop_codes = {s["stop_code"] for s in bart_stops if s.get("stop_code")}
        if stopCode not in valid_stop_codes:
            raise HTTPException(status_code=404, detail=f"Stop {stopCode} is not a valid BART stop")

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
        raise HTTPException(status_code=500, detail=f"Failed to fetch 511 SIRI data: {e}")