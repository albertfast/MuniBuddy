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
    Returns raw 511 SIRI BART data in standard StopMonitoring format,
    compatible with normalizeSiriData() used on frontend.
    """
    try:
        if agency.lower() not in ["bart", "ba"]:
            raise HTTPException(status_code=400, detail="Only BART agency is supported at this endpoint.")
        
        data = bart_service.get_bart_511_raw_data(stopCode)
        if not data:
            return {"message": f"No data received for stopCode: {stopCode}"}

        visits = data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", {}).get("MonitoredStopVisit", [])
        if not visits:
            return {
                "ServiceDelivery": {
                    "StopMonitoringDelivery": {
                        "MonitoredStopVisit": []
                    }
                }
            }

        # Return in full SIRI-compatible format
        return {
            "ServiceDelivery": {
                "StopMonitoringDelivery": {
                    "MonitoredStopVisit": visits
                }
            }
        }

    except Exception as e:
        log_debug(f"[BART POSITIONS] Error fetching for stopCode={stopCode}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch BART arrivals")
