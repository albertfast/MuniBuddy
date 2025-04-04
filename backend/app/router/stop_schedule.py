import os
import sys
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Path

# Add project root to sys.path for local module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.scheduler_service import SchedulerService

# Define FastAPI router
router = APIRouter()

# Create a global instance of SchedulerService
scheduler_service = SchedulerService()

@router.get(
    "/stop-schedule/{stop_id}",
    response_model=Dict[str, Any],  # Could be replaced with a custom Pydantic model
    summary="Get real-time and GTFS-based bus schedule for a stop"
)
async def get_stop_schedule_endpoint(
    stop_id: str = Path(..., description="The unique stop ID (e.g., '4212')")
):
    """
    Returns the upcoming bus schedule for a given stop.

    This includes:
    - Real-time predictions (via 511 API)
    - Fallback to static GTFS data if real-time is missing
    - Returns a structure with inbound/outbound arrival times

    Parameters:
        stop_id (str): The GTFS stop_id to lookup.

    Returns:
        Dict[str, Any]: A dictionary with 'inbound' and 'outbound' keys.

    Raises:
        400 - If stop_id is missing or invalid
        500 - On internal server error
    """
    if not stop_id:
        raise HTTPException(status_code=400, detail="Stop ID cannot be empty.")

    print(f"[API /stop-schedule] Request received for stop_id: {stop_id}")

    try:
        schedule = await scheduler_service.get_stop_schedule(stop_id)
        return schedule  # Expected format: {'inbound': [...], 'outbound': [...]}

    except HTTPException as http_exc:
        # Propagate known FastAPI exceptions
        raise http_exc
        
    # Add this missing exception handler:
    except Exception as e:
        print(f"[ERROR /stop-schedule] Internal error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
