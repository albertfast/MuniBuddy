from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import bus_service
from app.services.realtime_service import fetch_real_time_stop_data

router = APIRouter()

@router.get("/bus-positions/nearby")
async def get_nearby_bus_positions(
    lat: float = Query(...),
    lon: float = Query(...),
    bus_number: str = Query(...),
    agency: str = Query("SF")
):
    try:
        nearby_stops = await bus_service.get_nearby_buses(lat, lon, radius=0.2)
        results = []

        for stop in nearby_stops["stops"]:
            if not any(r["route_number"] == bus_number for r in stop["routes"]):
                continue

            stop_id = stop["gtfs_stop_id"]
            live_data = await fetch_real_time_stop_data(stop_id)
            live_match = next((b for b in (live_data.get("inbound", []) + live_data.get("outbound", [])) if b["route_number"] == bus_number), None)

            results.append({
                "stop_name": stop["stop_name"],
                "stop_id": stop["id"],
                "distance_miles": stop["distance_miles"],
                "live": live_match
            })

        return {"bus_number": bus_number, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {e}")
