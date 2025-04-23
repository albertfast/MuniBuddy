from fastapi import APIRouter, Query, HTTPException
from app.core.singleton import bart_service
from app.services.debug_logger import log_debug
from app.services.stop_helper import load_stops
from app.integrations.siri_api import fetch_siri_data_multi

router = APIRouter(prefix="/bart-positions", tags=["BART Positions"])

@router.get("/by-stop")
async def get_parsed_bart_by_stop(
    stopCode: str = Query(...),
    agency: str = Query("bart")
):
    try:
        all_stops = load_stops("bart")
        stop_info = next((s for s in all_stops if s["stop_code"] == stopCode or s["stop_id"] == stopCode), None)

        if not stop_info:
            raise HTTPException(status_code=404, detail=f"No stop found for code {stopCode}")

        # 🔁 Fetch real-time SIRI data using fetch_siri_data_multi
        raw_data = await fetch_siri_data_multi([stopCode], agency=agency)
        siri_data = raw_data.get(stopCode) or {}

        visits = siri_data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", [{}])[0].get("MonitoredStopVisit", [])
        if not visits:
            return {"stopCode": stopCode, "arrivals": [], "message": "No active arrivals found."}

        parsed = []
        for visit in visits:
            journey = visit.get("MonitoredVehicleJourney", {})
            call = journey.get("MonitoredCall", {})
            arrival_time = call.get("ExpectedArrivalTime") or call.get("AimedArrivalTime")
            direction = journey.get("DirectionRef", "").upper()

            parsed.append({
                "stop_id": stop_info.get("stop_id"),
                "stop_code": stopCode,
                "stop_name": stop_info.get("stop_name"),
                "direction": direction.lower(),
                "route_number": journey.get("PublishedLineName"),
                "destination": journey.get("DestinationName"),
                "arrival_time": arrival_time,
                "status": "Due",
                "minutes_until": None,
                "is_realtime": True,
                "vehicle": {
                    "lat": journey.get("VehicleLocation", {}).get("Latitude", ""),
                    "lon": journey.get("VehicleLocation", {}).get("Longitude", "")
                }
            })

        return {
            "stopCode": stopCode,
            "agency": stop_info["agency"],
            "arrivals": parsed,
            "count": len(parsed)
        }

    except Exception as e:
        log_debug(f"[BART POSITIONS] Error fetching for stopCode={stopCode}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch BART arrivals")

@router.get("/stop-arrivals/{stop_id}")
def get_bart_stop_arrivals(
    stop_id: str,
    lat: float = Query(None),
    lon: float = Query(None),
    radius: float = Query(0.15)
):
    try:
        return bart_service.get_stop_predictions(stop_id, lat, lon)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch arrivals: {e}")

@router.get("/nearby-stops")
async def get_nearby_bart_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(0.15)
):
    try:
        return await bart_service.get_real_time_arrivals(lat, lon, radius)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby BART stops: {e}")
