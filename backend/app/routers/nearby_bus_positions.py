from fastapi import APIRouter, HTTPException, Query
from app.core.singleton import bus_service

router = APIRouter()

@router.get("/bus-positions/nearby")
def get_nearby_bus_positions(
    lat: float = Query(...),
    lon: float = Query(...),
    bus_number: str = Query(...),
    agency: str = Query("muni")
):
    """
    Returns nearby stops with real-time info for a specific bus number and agency.
    """
    try:
        results = bus_service.get_nearby_buses(lat=lat, lon=lon, radius=0.2, agency=agency)

        filtered_results = []
        for stop in results["stops"]:
            buses = stop.get("buses", {})
            inbound = buses.get("inbound", [])
            outbound = buses.get("outbound", [])
            all_buses = inbound + outbound

            # Burada her bus için route_number ile filtreleme yapılıyor
            matching_buses = [b for b in all_buses if b.get("route_number") == bus_number]

            if matching_buses:
                stop_with_filtered_buses = {
                    "stop_id": stop.get("stop_id"),
                    "stop_code": stop.get("stop_code"),  # varsa bunu da taşıyalım
                    "stop_name": stop.get("stop_name"),
                    "distance_miles": stop.get("distance_miles"),
                    "buses": matching_buses
                }
                filtered_results.append(stop_with_filtered_buses)

        return {
            "bus_number": bus_number,
            "agency": agency,
            "results": filtered_results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {e}")
