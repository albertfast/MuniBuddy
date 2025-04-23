from fastapi import APIRouter, Query, HTTPException
from app.core.singleton import bart_service
from app.services.debug_logger import log_debug
from app.services.stop_helper import load_stops

router = APIRouter(prefix="/bart-positions", tags=["BART Positions"])

@router.get("/by-stop")
def get_parsed_bart_by_stop(
    stopCode: str = Query(...),
    agency: str = Query("bart")
):
    try:
        all_stops = load_stops("bart")
        stop_info = next((s for s in all_stops if s["stop_code"] == stopCode or s["stop_id"] == stopCode), None)

        if not stop_info:
            raise HTTPException(status_code=404, detail=f"No stop found for code {stopCode}")

        real_agency = stop_info["agency"]
        data = bart_service.realtime.fetch_real_time_stop_data(stopCode, agency=real_agency)

        visits = data.get("inbound", []) + data.get("outbound", [])
        if not visits:
            return {"stopCode": stopCode, "arrivals": [], "message": "No active arrivals found."}

        return {
            "stopCode": stopCode,
            "agency": real_agency,
            "arrivals": visits,
            "count": len(visits)
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
def get_nearby_bart_stops(
    lat: float = Query(..., description="Latitude of the user"),
    lon: float = Query(..., description="Longitude of the user"),
    radius: float = Query(0.15, description="Search radius in miles"),
    agency: Optional[str] = Query(None, description="Transit agency (e.g., muni or bart)")
):
    """
    Returns nearby stops from one or more agencies (Muni, BART) around a given location.
    If no agency is specified, returns stops from all GTFS agencies.
    """
    try:
        return bus_service.get_nearby_stops(lat, lon, radius, agency=agency)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby bart stops: {e}")