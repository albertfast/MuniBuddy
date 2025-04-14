from typing import Dict, Any
from app.services.stop_helper import load_stops, find_nearby_stops
from app.services.realtime_service import fetch_real_time_stop_data
from app.services.debug_logger import log_debug
from app.config import settings

class RealtimeBartService:
    def __init__(self):
        self.agency = "bart"

    async def fetch_real_time_stop_data(stop_code: str, agency: str = "muni", raw: bool = False) -> Dict[str, Any]:
        try:
            from app.integrations.siri_api import fetch_siri_data
            siri_data = await fetch_siri_data(stop_code, agency=agency)
            
            if raw:
                return siri_data  # ham 511 verisini direkt döndür

            # aksi halde mevcut inbound/outbound tahmin formatına çevir
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
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                    arrival_dt = datetime.fromisoformat(arrival_time.replace("Z", "+00:00"))
                    minutes_until = max(0, int((arrival_dt - now).total_seconds() / 60))
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

