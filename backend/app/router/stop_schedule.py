import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.bus_service import BusService

router = APIRouter()
bus_service = BusService()

@router.get("/api/stop-schedule/{stop_id}")
async def get_stop_schedule(stop_id: str, db: Session = Depends(get_db)):
    """
    Get schedule information for a specific stop
    """
    try:
        schedule = await bus_service.get_stop_schedule(stop_id)
        return schedule
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 