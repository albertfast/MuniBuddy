from typing import Dict, Any
from app.services.stop_helper import load_stops
from app.services.debug_logger import log_debug
from app.config import settings
from datetime import datetime, timezone
from app.integrations.siri_api import fetch_siri_data

raw_data = await fetch_siri_data("POWL", agency="bart")
print(raw_data)

class RealtimeBartService:
    def __init__(self):
        self.agency = "bart"

    @staticmethod
    async def fetch_real_time_stop_data(stop_code: str, agency: str = "muni", raw: bool = False) -> Dict[str, Any]:
        try:
            siri_data = await fetch_siri_data(stop_code, agency=agency)
            if raw:
                return siri_data

            parsed = {
                "inbound": [],
                "outbound": []
            }

            visits = siri_data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", {}).get("MonitoredStopVisit", [])
            for visit in visits:
                journey = visit.get("MonitoredVehicleJourney", {})
                call = journey.get("MonitoredCall", {})
                route = journey.get("PublishedLineName")
                destination = journey.get("DestinationName")
                arrival_time = call.get("ExpectedArrivalTime") or call.get("AimedArrivalTime")

                minutes_until = 0
                status = "Due"
                if arrival_time:
                    arrival_dt = datetime.fromisoformat(arrival_time.replace("Z", "+00:00"))
                    minutes_until = max(0, int((arrival_dt - datetime.now(timezone.utc)).total_seconds() / 60))
                    status = f"{minutes_until} min" if minutes_until > 0 else "Due"

                direction = journey.get("DirectionRef", "").upper()
                entry = {
                    "route_number": route,
                    "destination": destination,
                    "arrival_time": arrival_time,
                    "status": status,
                    "minutes_until": minutes_until,
                    "is_realtime": True
                }

                if direction == "IB":
                    parsed["inbound"].append(entry)
                else:
                    parsed["outbound"].append(entry)

            return parsed

        except Exception as e:
            log_debug(f"[511 API] Error parsing real-time stop data: {e}")
            return {"inbound": [], "outbound": []}

    async def fetch_stop_details(self, stop_id: str) -> Dict[str, Any]:
        return await self.get_bart_stop_details(stop_id)

    async def get_bart_stop_details(self, stop_id: str) -> Dict[str, Any]:
        """
        Gathers detailed BART stop information including platforms, routes, directions, real-time arrivals, and station metadata.
        """
        stops = load_stops("bart")
        stop = next(
            (s for s in stops if s["stop_id"] == stop_id or s.get("stop_code") == stop_id or s.get("stop_name") == stop_id),
            None
        )

        if not stop:
            return {"error": f"BART stop not found: {stop_id}"}

        details = {
            "stop_id": stop["stop_id"],
            "stop_name": stop.get("stop_name"),
            "stop_lat": stop.get("stop_lat"),
            "stop_lon": stop.get("stop_lon"),
            "location_type": stop.get("location_type"),
            "platform_code": stop.get("platform_code"),
            "parent_station": stop.get("parent_station"),
            "wheelchair_boarding": stop.get("wheelchair_boarding"),
            "stop_code": stop.get("stop_code"),
            "realtime": {},
            "routes": [],
            "directions": [],
            "lines": [],
        }

        try:
            realtime = await self.fetch_real_time_stop_data(stop.get("stop_code") or stop["stop_id"], agency="bart")
            details["realtime"] = realtime

            all_routes = set()
            all_directions = set()
            all_lines = set()

            for direction_key in ["inbound", "outbound"]:
                for entry in realtime.get(direction_key, []):
                    route = entry.get("route_number", "Unknown")
                    destination = entry.get("destination", "Unknown")
                    line = route.replace(" Line", "").strip()

                    all_routes.add(route)
                    all_directions.add(destination)
                    if line:
                        all_lines.add(line)

            details["routes"] = sorted(all_routes)
            details["directions"] = sorted(all_directions)
            details["lines"] = sorted(all_lines)

        except Exception as e:
            log_debug(f"[BART DETAIL] Failed to enrich {stop_id} with real-time data: {e}")
            details["realtime"] = {"error": str(e)}

        return details
