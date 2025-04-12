from fastapi import APIRouter, HTTPException
from app.services.realtime_service import fetch_real_time_stop_data

router = APIRouter()

@router.get("/stop-predictions/{stop_id}")
async def get_stop_predictions(stop_id: str):
    try:
        return await fetch_real_time_stop_data(stop_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Real-time prediction failed: {str(e)}")
