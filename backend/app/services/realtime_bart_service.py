from typing import Dict, Any
from datetime import datetime, timezone
from app.services.stop_helper import load_stops
from app.services.debug_logger import log_debug
from app.integrations.siri_api import fetch_siri_data
from app.config import settings
from app.services.schedule_service import SchedulerService

class RealtimeBartService:
    def __init__(self, scheduler: SchedulerService):
        log_debug("Initializing BartService...")
        self.scheduler = scheduler
        self.agency = settings.normalize_agency("bart")

    def _resolve_stop_code(self, identifier: str) -> str:
        stops = load_stops(self.agency)
        for stop in stops:
            if stop.get("stop_id") == identifier or stop.get("stop_code") == identifier or stop.get("stop_name") == identifier:
                return stop.get("stop_code") or stop.get("stop_id")
        return identifier 

    async def fetch_real_time_stop_data(self, stop_code: str, raw: bool = False) -> Dict[str, Any]:
        try:
            stop_code = self._resolve_stop_code(stop_code)
            siri_data = await fetch_siri_data(stop_code, agency=self.agency)
            if raw:
                return siri_data

            parsed = {"inbound": [], "outbound": []}
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
                    "is_realtime": True,
                    "vehicle": {
                        "lat": journey.get("VehicleLocation", {}).get("Latitude", ""),
                        "lon": journey.get("VehicleLocation", {}).get("Longitude", "")
                    }
                }

                if direction == "IB":
                    parsed["inbound"].append(entry)
                else:
                    parsed["outbound"].append(entry)

            return parsed

        except Exception as e:
            log_debug(f"[BART:fetch_real_time_stop_data] Fallback triggered for stop_code={stop_code}: {e}")
            return {"inbound": [], "outbound": []}
