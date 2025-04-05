import os
import sys
# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import essential modules first
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# Import your own modules
from app.db.database import get_db, SessionLocal
from app.services.bus_service import BusService  # Import BusService BEFORE using it

# Initialize DB connection and service
db = SessionLocal()
bus_service = BusService(db=db)  # Now BusService is defined

# Create the router
router = APIRouter()

@router.get("/stop-schedule/{stop_id}")
async def get_stop_schedule(stop_id: str, db: Session = Depends(get_db)):
    """
    Get schedule information for a specific stop
    """
    try:
        # Use the existing bus_service instance
        schedule = await bus_service.get_stop_schedule(stop_id)
        return schedule
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
