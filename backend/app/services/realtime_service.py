import httpx
import json
from datetime import datetime, timezone
import pytz
from typing import Optional, Dict, Any
from app.config import settings
from app.services.debug_logger import log_debug
from app.services.stop_helper import load_stops

API_KEY = settings.API_KEY
BASE_URL = settings.TRANSIT_511_BASE_URL


async def fetch_real_time_stop_data(stop_id: str, agency: str = "muni") -> Optional[Dict[str, Any]]:
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
        la_tz = pytz.timezone("America/Los_Angeles")
        now = datetime.now(tz=la_tz)
        arrival_time = la_tz.normalize(pytz.utc.localize(datetime.strptime(expected.split("Z")[0], "%Y-%m-%dT%H:%M:%S")))

        for visit in visits:
            journey = visit.get("MonitoredVehicleJourney", {})
            line_ref = journey.get("LineRef", "")
            published = journey.get("PublishedLineName", "Unknown")
            route_number = f"{line_ref} {published}".strip()
            destination = journey.get("DestinationName", "Unknown")
            direction = journey.get("DirectionRef", "").lower()
            call = journey.get("MonitoredCall", {})
            expected = call.get("ExpectedArrivalTime")
            aimed = call.get("AimedArrivalTime")

            arrival_time = None
            if expected:
                arrival_time = datetime.strptime(expected.split("Z")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(ZoneInfo("America/Los_Angeles"))
            elif aimed:
                arrival_time = datetime.strptime(aimed.split("Z")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(ZoneInfo("America/Los_Angeles"))

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
                "is_realtime": True
            }

            if direction == "1":
                inbound.append(bus_info)
            else:
                outbound.append(bus_info)

        return {"inbound": inbound, "outbound": outbound}

    except Exception as e:
        log_debug(f"[ERROR] fetch_real_time_stop_data failed: {e}")
        return {"inbound": [], "outbound": []}