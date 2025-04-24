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

@router.get("/vehicle-locations/by-stop")
async def get_vehicle_locations_by_stop(
    stopCode: str = Query(...),
    agency: str = Query(default="bart")
):
    try:
        norm_agency = settings.normalize_agency(agency, to_511=True)

        bart_stops = load_stops("bart")
        valid_stop_codes = {s["stop_code"] for s in bart_stops if s.get("stop_code")}
        if stopCode not in valid_stop_codes:
            raise HTTPException(status_code=404, detail=f"Stop {stopCode} is not a valid BART stop")

        stopmonitor_url = f"{settings.TRANSIT_511_BASE_URL}/StopMonitoring"
        params = {
            "api_key": settings.API_KEY,
            "agency": norm_agency,
            "stopCode": stopCode,
            "format": "json"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            stop_response = await client.get(stopmonitor_url, params=params)
            stop_data = stop_response.json()

        stop_visits = stop_data.get("ServiceDelivery", {}) \
                               .get("StopMonitoringDelivery", {}) \
                               .get("MonitoredStopVisit", [])

        vehicle_refs = list({visit.get("MonitoredVehicleJourney", {}).get("VehicleRef")
                             for visit in stop_visits if visit.get("MonitoredVehicleJourney", {}).get("VehicleRef")})

        if not vehicle_refs:
            return {"stopCode": stopCode, "vehicles": []}

        matched = await fetch_vehicle_locations_by_refs(vehicle_refs, agency=agency)
        return {"stopCode": stopCode, "vehicles": matched}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to match vehicle locations: {e}")


