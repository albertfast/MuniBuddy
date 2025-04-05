import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.db.database import SessionLocal

db = SessionLocal()
bus_service = BusService(db=db)


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.bus_service import BusService

router = APIRouter()

@router.get("/api/stop-schedule/{stop_id}")
async def get_stop_schedule(stop_id: str, db: Session = Depends(get_db)):
    """
    Get schedule information for a specific stop
    """
    try:
        # Pass the db session to BusService instance
        bus_service = BusService(db)
        schedule = await bus_service.get_stop_schedule(stop_id)
        return schedule
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
