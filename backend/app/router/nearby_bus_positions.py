from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from app.services.bus_service import BusService
from app.db.database import SessionLocal

db = SessionLocal()
bus_service = BusService(db=db)

router = APIRouter()

@router.get("/bus-positions/nearby")
async def get_nearby_bus_positions(
    lat: float = Query(..., description="Latitude of user"),
    lon: float = Query(..., description="Longitude of user"),
    bus_number: str = Query(..., description="Bus number like '5' or '38'"),
    agency: str = Query("SF", description="Agency code (SF for Muni, BART etc.)")
):
    """
    Get nearby bus positions (live if available, fallback to GTFS if not).
    This combines real-time vehicle positions and scheduled fallback.
    """
    try:
        nearby_stops = await bus_service.find_nearby_stops(lat, lon, radius_miles=0.2, limit=5)

        results = []
        for stop in nearby_stops:
            if not any(r["route_number"] == bus_number for r in stop["routes"]):
                continue  # skip stops that don't serve the requested bus

            stop_id = stop["gtfs_stop_id"]

            # First try live data
            live_data = await bus_service.fetch_real_time_stop_data(stop_id)
            live_buses = live_data.get("inbound", []) + live_data.get("outbound", []) if live_data else []

            live_match = next((b for b in live_buses if b["route_number"] == bus_number), None)

            # Then GTFS fallback
            schedule = await bus_service.get_stop_schedule(stop_id)
            gtfs_match = next((b for b in schedule.get("inbound", []) + schedule.get("outbound", []) if b["route_number"] == bus_number), None)

            results.append({
                "stop_name": stop["stop_name"],
                "stop_id": stop["id"],
                "distance_miles": stop["distance_miles"],
                "live": live_match,
                "scheduled": gtfs_match
            })

        if not results:
            return {"message": f"No nearby buses found for route {bus_number}"}

        return {
            "bus_number": bus_number,
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch nearby bus positions: {str(e)}")