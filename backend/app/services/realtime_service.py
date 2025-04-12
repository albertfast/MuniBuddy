import httpx
import json
from datetime import datetime
from typing import Optional, Dict, Any
from app.config import settings
from app.services.debug_logger import log_debug

API_KEY = settings.API_KEY
BASE_URL = settings.TRANSIT_511_BASE_URL


def fetch_real_time_stop_data(stop_id: str, agency: str = "SF") -> Optional[Dict[str, Any]]:
    """
    Fetch real-time arrival data for a specific stop from 511 API (synchronously).
    """
    try:
        url = f"{BASE_URL}/StopMonitoring"
        params = {
            "api_key": API_KEY,
            "agency": agency,
            "stopId": stop_id,
            "format": "json"
        }
        log_debug(f"[511 API] Requesting real-time data for stop: {stop_id} | agency: {agency}")
        response = httpx.get(url, params=params)
        response.raise_for_status()
        content = response.content.decode('utf-8-sig')
        data = json.loads(content)

        monitoring = data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", [])
        if isinstance(monitoring, list):
            monitoring = monitoring[0] if monitoring else {}

        stops = monitoring.get("MonitoredStopVisit", [])

        inbound = []
        outbound = []
        now = datetime.now()

        for stop in stops:
            journey = stop.get("MonitoredVehicleJourney", {})
            route_number = journey.get("PublishedLineName", "Unknown")
            destination = journey.get("DestinationName", "Unknown")
            direction = journey.get("DirectionRef", "").lower()
            call = journey.get("MonitoredCall", {})
            expected = call.get("ExpectedArrivalTime")
            aimed = call.get("AimedArrivalTime")

            arrival_time = None
            if expected:
                arrival_time = datetime.strptime(expected.split("Z")[0], "%Y-%m-%dT%H:%M:%S")
            elif aimed:
                arrival_time = datetime.strptime(aimed.split("Z")[0], "%Y-%m-%dT%H:%M:%S")

            if not arrival_time:
                continue

            if (arrival_time - now).total_seconds() > 7200:
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