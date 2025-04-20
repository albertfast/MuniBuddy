from fastapi import APIRouter, Query, HTTPException
from app.core.singleton import bart_service
from app.services.debug_logger import log_debug

router = APIRouter(prefix="/bart-positions", tags=["BART Positions"])

@router.get("/by-stop")
def get_bart_position_by_stop(
    stopCode: str = Query(..., description="BART stopCode like 'POWL'"),
    agency: str = Query("bart")
):
    """
    Returns parsed real-time BART arrivals for a given stop code using 511 SIRI API.
    """
    try:
        # BART only for now
        if agency.lower() not in ["bart", "ba"]:
            raise HTTPException(status_code=400, detail="Only BART agency is supported at this endpoint.")
        
        data = bart_service.get_bart_511_raw_data(stopCode)
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
