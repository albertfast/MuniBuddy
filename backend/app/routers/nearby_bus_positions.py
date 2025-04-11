# app/routers/nearby_bus_positions.py

from fastapi import APIRouter, HTTPException, Query
from app.services.realtime_service import fetch_stop_data
from app.services.schedule_service import get_static_schedule
from app.services.stop_helper import find_nearby_stops
from app.config import settings

router = APIRouter()

@router.get("/bus-positions/nearby")
async def get_nearby_bus_positions(
    lat: float = Query(...),
    lon: float = Query(...),
    bus_number: str = Query(...),
    agency: str = Query("muni")
):
    """
    Get nearby buses for a specific route, checking live predictions first and falling back to schedule.
    """
    try:
        gtfs_data = settings.get_gtfs_data(agency)
        nearby_stops = await find_nearby_stops(lat, lon, gtfs_data=gtfs_data, radius_miles=0.2, limit=5)
        results = []

        for stop in nearby_stops:
            if not any(r["route_number"] == bus_number for r in stop["routes"]):
                continue

            stop_id = stop["gtfs_stop_id"]
            live_data = await fetch_stop_data(stop_id, gtfs_data=gtfs_data)
            live_match = next((b for b in (live_data.get("inbound", []) + live_data.get("outbound", [])) if b["route_number"] == bus_number), None)

            schedule = get_static_schedule(stop_id, gtfs_data=gtfs_data)
            scheduled_match = next((b for b in (schedule.get("inbound", []) + schedule.get("outbound", [])) if b["route_number"] == bus_number), None)

            results.append({
                "stop_name": stop["stop_name"],
                "stop_id": stop["id"],
                "distance_miles": stop["distance_miles"],
                "live": live_match,
                "scheduled": scheduled_match
            })

        if not results:
            return {"message": f"No nearby buses found for route {bus_number}"}

        return {"bus_number": bus_number, "results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {e}")
