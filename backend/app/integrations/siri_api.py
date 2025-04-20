from typing import List, Dict, Any
import httpx
import asyncio
from app.config import settings
from app.services.debug_logger import log_debug
from app.services.stop_helper import load_stops, find_nearby_stops

def normalize_agency(agency: str) -> str:
    agency = agency.lower()
    if agency in ["sf", "muni", "sfmta"]:
        return "SF"
    elif agency in ["ba", "bart"]:
        return "BA"
    return agency.upper()

async def fetch_siri_data(lat: float, lon: float, agency: str = "muni", radius: float = 0.15) -> Dict[str, Any]:
    """
    Load stops from GTFS, find nearby stops, and fetch 511 real-time data in parallel for each stop_code.
    Returns parsed real-time results with route, destination, vehicle info, etc.
    """
    normalized_agency = settings.normalize_agency(agency)
    stops = load_stops(normalized_agency)
    nearby_stops = find_nearby_stops(lat, lon, stops, radius)

    stop_codes = [stop["stop_code"] or stop["stop_id"] for stop in nearby_stops]
    if not stop_codes:
        log_debug(f"[SIRI nearby] ❌ No stop codes found nearby for agency={normalized_agency}")
        return {"inbound": [], "outbound": []}

    url = f"{settings.TRANSIT_511_BASE_URL}/StopMonitoring"
    headers = {"accept": "application/json"}
    results = {"inbound": [], "outbound": []}

    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = []
        for stop_code in stop_codes:
            params = {
                "api_key": settings.API_KEY,
                "agency": normalize_agency(agency),
                "stopCode": stop_code,
                "format": "json"
            }
            tasks.append(client.get(url, params=params, headers=headers))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for stop_code, response in zip(stop_codes, responses):
            if isinstance(response, Exception):
                log_debug(f"[SIRI] ❌ Failed for stop {stop_code}: {response}")
                continue

            try:
                data = response.json()
                visits = data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", [{}])[0].get("MonitoredStopVisit", [])
                for visit in visits:
                    journey = visit.get("MonitoredVehicleJourney", {})
                    call = journey.get("MonitoredCall", {})
                    direction = journey.get("DirectionRef", "").upper()
                    entry = {
                        "stop_code": stop_code,
                        "route": journey.get("PublishedLineName"),
                        "destination": journey.get("DestinationName"),
                        "arrival_time": call.get("ExpectedArrivalTime") or call.get("AimedArrivalTime"),
                        "status": "Due",
                        "vehicle": journey.get("VehicleRef"),
                        "lat": journey.get("VehicleLocation", {}).get("Latitude"),
                        "lon": journey.get("VehicleLocation", {}).get("Longitude")
                    }
                    if direction == "IB":
                        results["inbound"].append(entry)
                    else:
                        results["outbound"].append(entry)

            except Exception as e:
                log_debug(f"[SIRI] ❌ JSON parse or visit extraction failed for {stop_code}: {e}")

    return results
