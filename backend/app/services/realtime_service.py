import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any
from app.config import settings
from app.integrations.siri_api import fetch_siri_data
from app.services.debug_logger import log_debug
from app.services.schedule_service import SchedulerService

scheduler = SchedulerService()

async def fetch_real_time_stop_data(stop_id: str, agency: str = "muni", lat: float = None, lon: float = None) -> Dict[str, Any]:
    """
    Try fetching real-time data using SIRI API first. If no data found, fallback to GTFS schedule.
    Returns structured inbound/outbound results with optional vehicle location.
    """
    try:
        normalized_agency = settings.normalize_agency(agency, to_511=True)
        log_debug(f"[REALTIME] Trying 511 API for stop_id={stop_id}, agency={normalized_agency}")

        siri_data = await fetch_siri_data(stop_code=stop_id, agency=normalized_agency)
        monitoring = siri_data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", {})
        visits = monitoring.get("MonitoredStopVisit", [])

        inbound = []
        outbound = []
        now = datetime.now(tz=ZoneInfo("America/Los_Angeles"))

        for visit in visits:
            try:
                journey = visit.get("MonitoredVehicleJourney", {})
                call = journey.get("MonitoredCall", {})
                route_number = f"{journey.get('LineRef', '')} {journey.get('PublishedLineName', '')}".strip()
                destination = journey.get("DestinationName", "Unknown")
                direction = journey.get("DirectionRef", "").lower()

                time_str = call.get("ExpectedArrivalTime") or call.get("AimedArrivalTime")
                if not time_str or "T" not in time_str:
                    log_debug(f"[WARN] Skipping visit with invalid time: {time_str}")
                    continue

                arrival_time = datetime.fromisoformat(time_str.replace("Z", "+00:00")).astimezone(ZoneInfo("America/Los_Angeles"))
                minutes_until = int((arrival_time - now).total_seconds() / 60)
                if minutes_until > 120:
                    continue

                bus_info = {
                    "route_number": route_number,
                    "destination": destination,
                    "arrival_time": arrival_time.strftime("%I:%M %p").lstrip("0"),
                    "status": "Due" if minutes_until <= 0 else f"{minutes_until} min",
                    "minutes_until": minutes_until,
                    "is_realtime": True,
                    "vehicle": {
                        "lat": journey.get("VehicleLocation", {}).get("Latitude", ""),
                        "lon": journey.get("VehicleLocation", {}).get("Longitude", "")
                    }
                }

                if direction == "1" or direction == "ib":
                    inbound.append(bus_info)
                else:
                    outbound.append(bus_info)

            except Exception as parse_err:
                log_debug(f"[REALTIME] ⚠️ Parse error for vehicle data: {parse_err}")
                continue

        if not inbound and not outbound:
            log_debug(f"[REALTIME] No data from 511 API, falling back to schedule for stop_id={stop_id}")
            return scheduler.get_schedule(stop_id, agency=settings.normalize_agency(agency))

        return {"inbound": inbound, "outbound": outbound}

    except Exception as e:
        log_debug(f"[REALTIME] ❌ Realtime fetch failed: {e}. Falling back to schedule.")
        return scheduler.get_schedule(stop_id, agency=settings.normalize_agency(agency))
