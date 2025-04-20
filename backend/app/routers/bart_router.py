from fastapi import APIRouter, Query, HTTPException
from app.core.singleton import bart_service
from app.services.debug_logger import log_debug

router = APIRouter(prefix="/bart-positions", tags=["BART Positions"])

@router.get("/by-stop")
async def get_parsed_bart_by_stop(
    stopCode: str = Query(...),
    agency: str = Query("bart")
):
    try:
        if agency.lower() not in ["bart", "ba"]:
            raise HTTPException(status_code=400, detail="Only BART agency is supported at this endpoint.")

        data = await bart_service.realtime.fetch_real_time_stop_data(stopCode)
        visits = data.get("inbound", []) + data.get("outbound", [])
        if not visits:
            return {"stopCode": stopCode, "arrivals": [], "message": "No active arrivals found."}

        return {
            "stopCode": stopCode,
            "agency": "bart",
            "arrivals": visits,
            "count": len(visits)
        }

    except Exception as e:
        log_debug(f"[BART POSITIONS] Error fetching for stopCode={stopCode}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch BART arrivals")


@router.get("/stop-arrivals/{stop_id}")
async def get_bart_stop_arrivals(
    stop_id: str,
    lat: float = Query(None),
    lon: float = Query(None),
    radius: float = Query(0.15)
):
    try:
        return await bart_service.get_stop_predictions(stop_id, lat, lon)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch arrivals: {e}")


@router.get("/nearby-stops")
def get_nearby_bart_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(0.15)
):
    try:
        return bart_service.get_real_time_arrivals(lat, lon, radius)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby BART stops: {e}")
