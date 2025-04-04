import os
import sys
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Path
import requests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.db.database import SessionLocal
session = SessionLocal() 

from app.services.bus_service import BusService

# Define FastAPI router
router = APIRouter()

# Create a global instance of BusService
bus_service = BusService(db=session)

@router.get(
    "/stop-schedule/{stop_id}",
    response_model=Dict[str, Any],
    summary="Get real-time and GTFS-based bus schedule for a stop"
)
async def get_stop_schedule_endpoint(
    stop_id: str = Path(..., description="The unique stop ID (e.g., '4212')")
):
    print(f"[REQUEST] /stop-schedule/{stop_id} called.")

    if not stop_id:
        print("[ERROR] No stop_id provided")
        raise HTTPException(status_code=400, detail="Stop ID cannot be empty.")

    try:
        print(f"[INFO] Calling BusService.get_stop_schedule with stop_id={stop_id}")
        schedule = await bus_service.get_stop_schedule(stop_id)
        print(f"[INFO] BusService.get_stop_schedule returned: {len(schedule['inbound'])} inbound, {len(schedule['outbound'])} outbound trips")
        return schedule

    except HTTPException as http_exc:
        print(f"[HTTP ERROR] {http_exc.detail}")
        raise http_exc
        
    except Exception as e:
        print(f"[ERROR] Internal error in stop-schedule endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/raw-511-data/{stop_id}")
async def get_raw_511_data(stop_id: str):
    """Get raw 511 API data for debugging."""
    api_url = f"{bus_service.base_url}/StopMonitoring"
    params = {
        "api_key": bus_service.api_key,
        "agency": bus_service.agency,
        "stopCode": stop_id,  # Try both stop_id and stopCode
        "format": "json"
    }
    try:
        response = requests.get(api_url, params=params)
        return {
            "status_code": response.status_code,
            "data": response.json() if response.status_code == 200 else None
        }
    except Exception as e:
        return {"error": str(e)}

