from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from app.services.stop_helper import load_stops, calculate_distance

router = APIRouter()

@router.get("/nearby-stops")
def get_combined_nearby_stops(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(0.15),
    agency: Optional[str] = Query(None)
):
    try:
        all_stops: List[Dict[str, Any]] = load_stops()
        filtered: List[Dict[str, Any]] = []

        for stop in all_stops:
            if agency and stop["agency"].lower() != agency.lower():
                continue
            dist = calculate_distance(lat, lon, stop["stop_lat"], stop["stop_lon"])
            if dist <= radius:
                stop["distance_miles"] = round(dist, 3)
                filtered.append(stop)

        filtered.sort(key=lambda x: x["distance_miles"])
        return filtered

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch combined stops: {str(e)}")
