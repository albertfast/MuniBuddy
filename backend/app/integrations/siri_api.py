from typing import List, Dict
import httpx
import asyncio
from app.config import settings
from typing import List, Dict, Any
from app.services.debug_logger import log_debug

def normalize_agency(agency: str) -> str:
    agency = agency.lower()
    if agency in ["sf", "muni", "sfmta"]:
        return "SF"
    elif agency in ["ba", "bart"]:
        return "BA"
    return agency.upper()

async def fetch_siri_data(stops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = []
        for stop in stops:
            stop_code = stop.get("stop_code") or stop.get("stop_id")
            agency_code = normalize_agency(stop.get("agency", "SF"))
            params = {
                "api_key": settings.API_KEY,
                "agency": agency_code,
                "stopCode": stop_code,
                "format": "json"
            }
            tasks.append(client.get(f"{settings.TRANSIT_511_BASE_URL}/StopMonitoring", params=params))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for stop, resp in zip(stops, responses):
            stop_code = stop.get("stop_code") or stop.get("stop_id")
            if isinstance(resp, Exception):
                log_debug(f"[SIRI MULTI] ❌ Error for stop {stop_code}: {resp}")
                stop["arrivals"] = []
                stop["error"] = str(resp)
            else:
                try:
                    data = resp.json()
                    visits = data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", [{}])[0].get("MonitoredStopVisit", [])
                    arrivals = []
                    for v in visits:
                        journey = v.get("MonitoredVehicleJourney", {})
                        call = journey.get("MonitoredCall", {})
                        arrivals.append({
                            "route": journey.get("PublishedLineName"),
                            "destination": journey.get("DestinationName"),
                            "arrival_time": call.get("ExpectedArrivalTime") or call.get("AimedArrivalTime"),
                            "vehicle_id": journey.get("VehicleRef"),
                            "direction": journey.get("DirectionRef", "").upper(),
                            "platform": call.get("StopPointName"),
                            "lat": journey.get("VehicleLocation", {}).get("Latitude"),
                            "lon": journey.get("VehicleLocation", {}).get("Longitude")
                        })
                    stop["arrivals"] = arrivals
                except Exception as e:
                    log_debug(f"[SIRI MULTI] ❌ JSON parse failed for stop={stop_code}: {e}")
                    stop["arrivals"] = []
                    stop["error"] = "Invalid JSON"

            results.append(stop)

    return results
