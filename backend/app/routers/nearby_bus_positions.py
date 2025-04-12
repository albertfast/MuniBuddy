from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import bus_service

router = APIRouter()

@router.get("/bus-positions/nearby")
def get_nearby_bus_positions(
    lat: float = Query(...),
    lon: float = Query(...),
    bus_number: str = Query(...),
    agency: str = Query("muni")  # Default agency
):
    """
    Returns nearby stops with real-time info for a specific bus number and agency.
    """
    try:
        results = bus_service.get_nearby_buses(lat=lat, lon=lon, radius=0.2, agency=agency)

        filtered_results = []
        for stop in results["stops"]:
            all_buses = stop.get("buses", {})
            inbound = all_buses.get("inbound", [])
            outbound = all_buses.get("outbound", [])
            combined = inbound + outbound

            if any(bus.get("route_number") == bus_number for bus in combined):
                filtered_results.append(stop)

        return {
            "bus_number": bus_number,
            "agency": agency,
            "results": filtered_results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {e}")
