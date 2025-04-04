import os
import sys
# Ensure the project root is in the path
# Adjust the number of '..' based on your test file location relative to the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session # Session importu genelde gerekli olmaz eğer db'yi doğrudan kullanmıyorsa
# from app.db.database import get_db # get_db Depends'i kaldırıldı, find_nearby_stops DB kullanmıyor gibi görünüyor
from app.services.bus_service import BusService
from typing import List, Dict, Any # Tip ipuçları için

router = APIRouter()

# --- BusService Instance ---
# Option 1: Simple global instance (Okay for smaller apps, ensure thread-safety if needed)
# BusService() instance might load GTFS data, doing it once here is better than in each request.
bus_service = BusService()

# Option 2: FastAPI Dependency Injection (Recommended for larger/testable apps)
# async def get_bus_service():
#     # You could implement caching or more complex logic here if needed
#     # For now, let's assume BusService init handles loading efficiently
#     yield BusService() # Or yield a shared instance

@router.get("/nearby-stops", response_model=List[Dict[str, Any]]) # Add response_model for clarity
async def get_nearby_stops(
    lat: float = Query(..., description="Latitude of the search center"),
    lon: float = Query(..., description="Longitude of the search center"),
    radius_miles: float = Query(0.15, gt=0, le=1.0, description="Search radius in miles (0.1 to 1.0)"),
    limit: int = Query(10, gt=0, le=50, description="Maximum number of stops to return (1 to 50)") # Add limit parameter
    # db: Session = Depends(get_db) # Removed: find_nearby_stops doesn't seem to use db directly
    # bus_service: BusService = Depends(get_bus_service) # Use this if using Option 2 above
):
    """
    Get nearby transit stops within the specified radius, sorted by distance.
    Returns basic stop information including associated routes.
    """
    print(f"[API /nearby-stops] Request: lat={lat}, lon={lon}, radius={radius_miles}, limit={limit}")
    try:
        # --- CORRECTED FUNCTION CALL ---
        # Call find_nearby_stops to get only the list of stops and basic info
        nearby_stops_list: List[Dict[str, Any]] = await bus_service.find_nearby_stops(
            lat, lon, radius_miles, limit=limit # Pass the limit
        )
        # -------------------------------

        # find_nearby_stops already returns a list of dicts
        if not nearby_stops_list:
             print(f"[API /nearby-stops] No stops found.")
             # Returning an empty list is standard for "not found" in list endpoints
             return []

        print(f"[API /nearby-stops] Found {len(nearby_stops_list)} stops.")
        return nearby_stops_list

    except Exception as e:
        # Log the actual error for debugging on the server
        print(f"[ERROR /nearby-stops] Failed to find nearby stops: {e}")
        # Raise a generic server error to the client
        raise HTTPException(status_code=500, detail="An internal error occurred while searching for nearby stops.")