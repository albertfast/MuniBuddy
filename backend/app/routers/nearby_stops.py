
# from fastapi import APIRouter, Query, HTTPException
# from app.core.singleton import bus_service, bart_service

# router = APIRouter()

# @router.get("/nearby-stops")
# def get_combined_nearby_stops(
#     lat: float = Query(...),
#     lon: float = Query(...),
#     radius: float = Query(0.15),
#     agency: str = Query(None)
# ):
#     try:
#         if agency:
#             agency = agency.lower()
#             if agency in ["muni", "sf", "sfmta"]:
#                 return bus_service.get_nearby_stops(lat, lon, radius, agency="muni")
#             elif agency in ["bart", "ba"]:
#                 return bart_service.get_nearby_stops(lat, lon, radius)
#             return []

#         muni_stops = bus_service.get_nearby_stops(lat, lon, radius, agency="muni")
#         bart_stops = bart_service.get_nearby_stops(lat, lon, radius)
#         all_stops = muni_stops + bart_stops
#         all_stops.sort(key=lambda s: s.get("distance_miles", 999))
#         return all_stops

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to fetch nearby stops: {e}")
