import os
import sys
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Path, Depends # Added Depends
import json

# Ensure the project root is in the path
try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from app.services.bus_service import BusService
    # Import settings if needed for dependency, etc.
    # from app.config import settings
except ImportError as e:
     print(f"[ERROR] Failed to import BusService or settings in router: {e}")
     # Handle this critical error - maybe raise?
     # For now, define a dummy BusService if needed for the script to load
     class BusService: async def get_stop_schedule(self, stop_id): return {'inbound':[], 'outbound':[]}


# --- Dependency Injection for BusService (Recommended) ---
# Create a single instance to be shared across requests
# This ensures GTFS is loaded only once.
bus_service_instance = BusService()

async def get_bus_service() -> BusService:
     # You could add logic here if needed (e.g., check health)
     # but simply returning the global instance works for sharing.
     return bus_service_instance

# --- Router Definition ---
router = APIRouter(
    prefix="/api/v1", # Optional: Add prefix for all routes in this file
    tags=["Schedules"] # Tag for OpenAPI documentation
)

@router.get(
    "/stop-schedule/{stop_id}",
    response_model=Dict[str, Any], # Consider a more specific Pydantic model later
    summary="Get Schedule for a Specific Stop",
    description="Retrieves real-time arrival predictions if available, otherwise falls back to the static GTFS schedule for the given stop ID. Results are cached."
)
async def get_stop_schedule_endpoint(
    stop_id: str = Path(..., description="The unique stop ID (e.g., '1234' or '4212').", regex="^[a-zA-Z0-9_]+$"), # Added regex validation
    # Inject the shared BusService instance
    service: BusService = Depends(get_bus_service)
):
    """
    Endpoint to fetch the upcoming bus schedule for a single stop.
    """
    if not stop_id:
        # Path validation might catch this, but good to double-check
        raise HTTPException(status_code=400, detail="Stop ID path parameter cannot be empty.")

    print(f"[API /stop-schedule] Request received for stop_id: {stop_id}")
    try:
        # Call the service method using the injected instance
        schedule = await service.get_stop_schedule(stop_id)

        # The service method now always returns a dict, check content if needed
        # but usually just return what the service gives.
        print(f"[API /stop-schedule] Returning schedule for {stop_id}. Inbound: {len(schedule.get('inbound',[]))}, Outbound: {len(schedule.get('outbound',[]))}")
        return schedule

    except HTTPException as http_exc:
         # Re-raise exceptions that are already FastAPI/HTTP specific
         print(f"[API /stop-schedule] Re-raising HTTPException for {stop_id}: {http_exc.status_code} - {http_exc.detail}")
         raise http_exc
    except Exception as e:
        # Catch-all for unexpected errors in the service or endpoint logic
        print(f"[ERROR /stop-schedule] Unexpected error processing request for stop {stop_id}: {e}")
        # import traceback # Uncomment for detailed stack trace in logs
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An internal server error occurred.") # Avoid leaking internal details


# --- Optional: Include the raw 511 data endpoint for debugging ---
# Needs 'requests' library if used synchronously here, or use httpx from service
import requests # Add sync requests if needed for this specific debug endpoint

@router.get(
    "/debug/raw-511-stop/{stop_id}",
    tags=["Debugging"],
    summary="Get Raw 511 StopMonitoring Response (Debug Only)"
)
async def get_raw_511_data(
    stop_id: str = Path(..., description="The stop code/ID to query."),
    service: BusService = Depends(get_bus_service) # Get service to access base_url, api_key
    ):
    """
    **Debugging Endpoint:** Fetches and returns the raw JSON response
    from the 511 StopMonitoring API for a given stop code.
    Uses synchronous requests for simplicity in this debug route.
    """
    if not service.api_key:
        raise HTTPException(status_code=503, detail="511 API Key not configured on server.")

    api_url = f"{service.base_url}/StopMonitoring"
    params = {
        "api_key": service.api_key,
        "agency": "SF", # Assuming Muni
        "stopCode": stop_id,
        "format": "json"
    }
    print(f"[DEBUG /raw-511-stop] Requesting {api_url} with params {params}")
    try:
        # Using sync requests here for simplicity in a debug route
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status() # Check for HTTP errors
        # Try decoding, handling potential BOM
        try: data = response.json()
        except json.JSONDecodeError:
             cleaned_text = response.text.encode().decode('utf-8-sig')
             data = json.loads(cleaned_text)
        return {
            "request_url": response.url, # Show the final requested URL
            "status_code": response.status_code,
            "data": data
        }
    except requests.exceptions.RequestException as req_err:
         print(f"[ERROR /raw-511-stop] Request failed: {req_err}")
         raise HTTPException(status_code=503, detail=f"Failed to fetch data from 511 API: {req_err}")
    except json.JSONDecodeError as json_err:
        print(f"[ERROR /raw-511-stop] JSON decode failed: {json_err}")
        raise HTTPException(status_code=500, detail=f"Failed to decode 511 API response: {json_err}")
    except Exception as e:
        print(f"[ERROR /raw-511-stop] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
