from fastapi import APIRouter, Query, HTTPException
from app.core.singleton import bart_service
from app.services.debug_logger import log_debug

router = APIRouter(prefix="/bart-positions", tags=["BART Positions"])

@router.get("/bart/nearby-stops")
def get_nearby_bart_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(0.15)
):
    """
    Returns parsed real-time BART arrivals for a given stop code using 511 SIRI API.
    """
    try:
        # BART only for now
        if agency.lower() not in ["bart", "ba"]:
            raise HTTPException(status_code=400, detail="Only BART agency is supported at this endpoint.")
        
        data = await bart_service.get_bart_511_raw_data(stopCode)
        if not data:
            return {"message": f"No data received for stopCode: {stopCode}"}

        visits = data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", {}).get("MonitoredStopVisit", [])
        if not visits:
            return {"stopCode": stopCode, "arrivals": [], "message": "No active arrivals found."}

        arrivals = []
        for v in visits:
            journey = v.get("MonitoredVehicleJourney", {})
            call = journey.get("MonitoredCall", {})
            arrivals.append({
                "route": journey.get("PublishedLineName"),
                "destination": journey.get("DestinationName"),
                "vehicle_id": journey.get("VehicleRef"),
                "lat": journey.get("VehicleLocation", {}).get("Latitude"),
                "lon": journey.get("VehicleLocation", {}).get("Longitude"),
                "expected": call.get("ExpectedArrivalTime"),
                "aimed": call.get("AimedArrivalTime"),
                "stop_name": call.get("StopPointName"),
                "at_stop": call.get("VehicleAtStop"),
            })

        return {
            "stopCode": stopCode,
            "agency": "bart",
            "arrivals": arrivals,
            "count": len(arrivals)
        }

    except Exception as e:
        log_debug(f"[BART POSITIONS] Error fetching for stopCode={stopCode}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch BART arrivals")
        
@router.get("/bart/stop-arrivals/{stop_id}")
async def get_bart_stop_arrivals(
    stop_id: str,
    lat: float = Query(None),
    lon: float = Query(None),
    radius: float = Query(0.15)
):
    """
    Returns real-time arrivals (or fallback schedule) for a specific BART stop.
    """
    try:
        return await bart_service.get_real_time_arrivals(stop_id, lat, lon, radius)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch arrivals: {e}")

@router.get("/bart/route-stops/{route_id}")
def get_bart_route_stops(
    route_id: str,
    direction_id: int = 0
):
    """
    Returns list of stops for a given BART route and direction.
    """
    try:
        return bart_service.get_route_stops(route_id, direction_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch route stops: {e}")
