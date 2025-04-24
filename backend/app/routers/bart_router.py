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

        # 1. Stop doğrulama (GTFS)
        bart_stops = load_stops("bart")
        valid_stop_codes = {s["stop_code"] for s in bart_stops if s.get("stop_code")}
        if stopCode not in valid_stop_codes:
            raise HTTPException(status_code=404, detail=f"Stop {stopCode} is not a valid BART stop")

        # 2. StopMonitoring verisini al
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

        # 3. StopMonitoring'den eşleşme için key çıkar
        valid_keys = set()
        for visit in stop_visits:
            mvj = visit.get("MonitoredVehicleJourney", {})
            fr = mvj.get("FramedVehicleJourneyRef", {})
            line = mvj.get("LineRef")
            jid = fr.get("DatedVehicleJourneyRef")
            if line and jid:
                valid_keys.add((line, jid))

        if not valid_keys:
            return {"stopCode": stopCode, "vehicles": []}

        # 4. VehicleMonitoring çağrısı (tüm araçlar)
        vehiclemonitor_url = f"{settings.TRANSIT_511_BASE_URL}/VehicleMonitoring"
        vehicle_params = {
            "api_key": settings.API_KEY,
            "agency": norm_agency,
            "format": "json"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            vehicle_response = await client.get(vehiclemonitor_url, params=vehicle_params)
            vehicle_data = vehicle_response.json()

        vehicle_activities = vehicle_data.get("ServiceDelivery", {}) \
                                         .get("VehicleMonitoringDelivery", [{}])[0] \
                                         .get("VehicleActivity", [])

        matched = []
        for activity in vehicle_activities:
            mvj = activity.get("MonitoredVehicleJourney", {})
            fr = mvj.get("FramedVehicleJourneyRef", {})
            line = mvj.get("LineRef")
            jid = fr.get("DatedVehicleJourneyRef")
            vehicle = mvj.get("VehicleRef")
            location = mvj.get("VehicleLocation")

            if (line, jid) in valid_keys and vehicle and location:
                matched.append({
                    "vehicle_id": vehicle,
                    "line": line,
                    "latitude": location.get("Latitude"),
                    "longitude": location.get("Longitude")
                })

        return {"stopCode": stopCode, "vehicles": matched}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to match vehicle locations: {e}")
