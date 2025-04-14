from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import bart_service
from app.services.realtime_service import fetch_real_time_stop_data

router = APIRouter()

@router.get("/stop-predictions/{stop_id}")
async def get_stop_predictions(
    stop_id: str,
    lat: float = Query(None),
    lon: float = Query(None),
    agency: str = Query("muni")
):
    try:
        agency = agency.lower()
        if agency in ["bart", "ba"]:
            return await bart_service.get_real_time_arrivals(stop_id, lat, lon)
        return await fetch_real_time_stop_data(stop_id, agency=agency)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Real-time prediction failed: {str(e)}")
