from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import bart_service
from app.services.realtime_service import fetch_real_time_stop_data

router = APIRouter()

def normalize_agency(agency_raw: str) -> str:
    agency_raw = agency_raw.lower()
    if agency_raw in ["sf", "sfmta", "muni"]:
        return "muni"
    elif agency_raw in ["ba", "bart"]:
        return "bart"
    return agency_raw

@router.get("/stop-predictions/{stop_id}")
async def get_stop_predictions(
    stop_id: str,
    lat: float = Query(None),
    lon: float = Query(None),
    agency: str = Query("muni"),
    detailed: bool = Query(False)
):
    try:
        agency = normalize_agency(agency)

        if agency == "bart":
            if detailed:
                return await bart_service.get_bart_stop_details(stop_id)
            return await bart_service.get_real_time_arrivals(stop_id, lat, lon)

        # Muni
        return await fetch_real_time_stop_data(stop_id, agency=agency)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Real-time prediction failed: {str(e)}")
