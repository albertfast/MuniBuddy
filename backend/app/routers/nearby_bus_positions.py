# from typing import Optional
# from app.core.singleton import bus_service 
# from fastapi import APIRouter, Query, HTTPException
# from app.config import settings
# from app.services.debug_logger import log_debug
# from app.routers.nearby_stops import get_combined_nearby_stops
# import httpx

# router = APIRouter()

# def normalize_agency(agency: str) -> str:
#     agency = agency.lower()
#     if agency in ["sf", "muni", "sfmta"]:
#         return "SF"
#     elif agency in ["ba", "bart"]:
#         return "BA"
#     return agency.upper()

# @router.get("/bus-positions/by-stop")
# async def get_bus_positions_by_stop(
#     stopCode: str = Query(..., description="GTFS stop_code or stop_id"),
#     agency: str = Query("muni", description="Agency name (e.g., muni, SFMTA, bart)")
# ):
#     """
#     Fetch raw SIRI StopMonitoring data for a single stopCode & agency.
#     Returns 511 SIRI-compliant JSON.
#     """
#     try:
#         norm_agency = normalize_agency(agency)
#         log_debug(f"[API] Fetching SIRI StopMonitoring for stopCode={stopCode}, agency={norm_agency}")

#         url = f"{settings.TRANSIT_511_BASE_URL}/StopMonitoring"
#         params = {
#             "api_key": settings.API_KEY,
#             "agency": norm_agency,
#             "stopCode": stopCode,
#             "format": "json"
#         }

#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.get(url, params=params)
#             response.raise_for_status()
#             return response.json()

#     except Exception as e:
#         log_debug(f"[API] ❌ SIRI fetch failed for stopCode={stopCode}, agency={agency}: {e}")
#         raise HTTPException(status_code=500, detail=f"Failed to fetch 511 SIRI data: {e}")



