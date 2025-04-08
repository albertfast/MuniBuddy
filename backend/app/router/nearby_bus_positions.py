from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import bus_service

router = APIRouter()

@router.get("/bus-positions/nearby")
async def get_nearby_bus_positions(
    lat: float = Query(...),
    lon: float = Query(...),
    bus_number: str = Query(...),
    agency: str = Query("SF")
):
    """
    Get nearby buses (live if possible, fallback to GTFS)
    """
    try:
        nearby_stops = await bus_service.find_nearby_stops(lat, lon, radius_miles=0.2, limit=5)
        results = []

        for stop in nearby_stops:
            if not any(r["route_number"] == bus_number for r in stop["routes"]):
                continue

            stop_id = stop["gtfs_stop_id"]
            live_data = await bus_service.fetch_real_time_stop_data(stop_id)
            live_match = next((b for b in (live_data.get("inbound", []) + live_data.get("outbound", [])) if b["route_number"] == bus_number), None)

            schedule = await bus_service.get_stop_schedule(stop_id)
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