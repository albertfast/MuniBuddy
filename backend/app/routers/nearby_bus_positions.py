from fastapi import APIRouter, HTTPException, Query
from app.services.realtime_service import fetch_real_time_stop_data
from app.services.stop_helper import load_stops

router = APIRouter()

@router.get("/bus-positions/by-stop")
def get_real_time_buses_by_stop(
    stop_code: str = Query(..., description="GTFS stop_code (ex: 14212)"),
    agency: str = Query("muni", description="Transit agency (default: muni)"),
    bus_number: str = Query(None, description="Optional route number to filter")
):
    """
    Returns real-time bus arrivals for a specific stop using stop_code and agency.
    """
    try:
        stops = load_stops(agency)
        matched_stop = next((s for s in stops if s.get("stop_code") == stop_code), None)

        if not matched_stop:
            raise HTTPException(status_code=404, detail=f"Stop with stop_code {stop_code} not found.")

        realtime_data = fetch_real_time_stop_data(matched_stop, agency)

        buses = []
        for direction in ["inbound", "outbound"]:
            for bus in realtime_data.get(direction, []):
                if bus_number and bus.get("route_number") != bus_number:
                    continue
                buses.append({
                    "route_number": bus.get("route_number"),
                    "destination": bus.get("destination"),
                    "arrival_time": bus.get("arrival_time"),
                    "status": bus.get("status"),
                    "minutes_until": bus.get("minutes_until"),
                    "is_realtime": bus.get("is_realtime"),
                    "direction": direction
                })

        return {
            "stop_code": stop_code,
            "stop_name": matched_stop.get("stop_name"),
            "buses": buses
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch real-time buses: {e}")
