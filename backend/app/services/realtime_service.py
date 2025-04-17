import httpx
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any
from app.config import settings
from app.services.stop_helper import load_stops
from app.services.debug_logger import log_debug


API_KEY = settings.API_KEY
BASE_URL = settings.TRANSIT_511_BASE_URL


async def fetch_real_time_stop_data(stop_id: str, agency: str = "muni") -> Dict[str, Any]:
    """
    Fetch real-time arrival data by finding stop_code via load_stops(),
    then calling 511 API with it.
    Returns parsed inbound/outbound data with route number, arrival time, etc.
    """
    try:
        stops = load_stops(agency)
        stop = next((s for s in stops if s["stop_id"] == stop_id or s.get("stop_code") == stop_id), None)

        if not stop:
            log_debug(f"[ERROR] Stop not found in GTFS for id/code: {stop_id}")
            return {"inbound": [], "outbound": []}

        stop_code = stop.get("stop_code")
        if not stop_code:
            log_debug(f"[ERROR] No stop_code found for stop_id={stop_id}")
            return {"inbound": [], "outbound": []}

        url = f"{BASE_URL}/StopMonitoring"
        params = {
            "api_key": API_KEY,
            "agency": "SF",
            "stopCode": stop_code,
            "format": "json"
        }

        log_debug(f"[511 API] Requesting real-time data for stop_code={stop_code} ({stop.get('stop_name')})")

        response = httpx.get(url, params=params)
        response.raise_for_status()

        content = response.content.decode('utf-8-sig')
        data = json.loads(content)

        monitoring = data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", [])
        if isinstance(monitoring, list):
            monitoring = monitoring[0] if monitoring else {}

        visits = monitoring.get("MonitoredStopVisit", [])

        inbound = []
        outbound = []
        now = datetime.now(tz=ZoneInfo("America/Los_Angeles"))

        for visit in visits:
            try:
                journey = visit.get("MonitoredVehicleJourney", {})
                line_ref = journey.get("LineRef", "")
                published = journey.get("PublishedLineName", "Unknown")
                route_number = f"{line_ref} {published}".strip()
                destination = journey.get("DestinationName", "Unknown")
                direction = journey.get("DirectionRef", "").lower()
                call = journey.get("MonitoredCall", {})
                expected = call.get("ExpectedArrivalTime")
                aimed = call.get("AimedArrivalTime")

                time_str = expected or aimed
                if not time_str or "T" not in time_str:
                    log_debug(f"[WARN] Skipping visit due to invalid time_str: {time_str}")
                    continue

                raw_time = time_str.replace("Z", "")[:19]
                arrival_time = datetime.strptime(raw_time, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(ZoneInfo("America/Los_Angeles"))

                if not arrival_time or (arrival_time - now).total_seconds() > 7200:
                    continue

                minutes_until = int((arrival_time - now).total_seconds() / 60)
                status = "Due" if minutes_until <= 0 else f"{minutes_until} min"

                bus_info = {
                    "route_number": route_number,
                    "destination": destination,
                    "arrival_time": arrival_time.strftime("%I:%M %p").lstrip("0"),
                    "status": status,
                    "minutes_until": minutes_until,
                    "is_realtime": True,
                    "vehicle": {
                        "lat": journey.get("VehicleLocation", {}).get("Latitude"),
                        "lon": journey.get("VehicleLocation", {}).get("Longitude")
                    }
                }

                if direction == "1":
                    inbound.append(bus_info)
                else:
                    outbound.append(bus_info)

            except Exception as inner_err:
                log_debug(f"[WARN] Skipping malformed vehicle entry: {inner_err}")
                continue

        return {"inbound": inbound, "outbound": outbound}

    except Exception as e:
        log_debug(f"[ERROR] fetch_real_time_stop_data failed: {e}")
        raise