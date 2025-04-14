from fastapi import APIRouter, Query, HTTPException
from app.services.realtime_bart_service import RealtimeBartService

router = APIRouter()
realtime_bart = RealtimeBartService()

@router.get("/bart/monitor-stop")
async def monitor_bart_stop(stopCode: str = Query(...)):
    """
    Return full 511 SIRI response for a given BART stopCode.
    Useful for debugging or frontend advanced visualization.
    """
    try:
        return await realtime_bart.get_bart_511_raw_data(stopCode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch BART monitor data: {e}")
