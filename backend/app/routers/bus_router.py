# backend/app/routers/bus_router.py
from fastapi import APIRouter, Query, HTTPException
from app.config import settings
from app.services.stop_helper import load_stops
import httpx

router = APIRouter(prefix="/bus-positions", tags=["MUNI Bus Positions"])

@router.get("/by-stop")
async def get_parsed_bus_by_stop(
    stopCode: str = Query(...),
    agency: str = Query(default="muni")
):
    try:
        norm_agency = settings.normalize_agency(agency, to_511=True)

        muni_stops = load_stops("muni")
        valid_stop_codes = {s["stop_code"] for s in muni_stops if s.get("stop_code")}
        if stopCode not in valid_stop_codes:
            raise HTTPException(status_code=404, detail=f"Stop {stopCode} is not a valid MUNI stop")

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
