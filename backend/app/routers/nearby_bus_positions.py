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
    Returns nearby stops with real-time info for a specific bus number.
    """
    try:
        # Get nearby buses using the consolidated bus_service logic
        results = await bus_service.get_nearby_buses(lat=lat, lon=lon, radius=0.2)

        # Filter only those stops matching the requested bus number
        filtered_results = []
        for stop in results["stops"]:
            if any(r["route_number"] == bus_number for r in stop["routes"]):
                filtered_results.append(stop)

        return {
            "bus_number": bus_number,
            "results": filtered_results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {e}")
