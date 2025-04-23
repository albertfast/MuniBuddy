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
        arrivals = await bart_service.get_real_time_arrival_by_stop(stopCode, agency)

        if not arrivals["inbound"] and not arrivals["outbound"]:
            return {"stopCode": stopCode, "arrivals": [], "message": "No active arrivals found."}

        return {
            "stopCode": stopCode,
            "agency": agency,
            "arrivals": arrivals["inbound"] + arrivals["outbound"],
            "count": len(arrivals["inbound"]) + len(arrivals["outbound"])
        }
    except Exception as e:
        log_debug(f"[BART POSITIONS] Error fetching for stopCode={stopCode}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch BART arrivals")

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
