import httpx
from typing import Optional, Dict, Any
from datetime import datetime
from app.config import settings
from app.services.debug_logger import log_debug

API_KEY = settings.API_KEY
BASE_URL = settings.TRANSIT_511_BASE_URL


async def fetch_real_time_stop_data(stop_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches real-time bus arrival data from 511.org API for a given stop.

    Args:
        stop_id (str): The stop ID (ex: 4212 or 14212)

    Returns:
        dict with 'inbound' and 'outbound' bus info lists
    """
    log_debug(f"Fetching real-time data for stop {stop_id}")

    params = {
        "api_key": API_KEY,
        "agency": "SF",  # Can be made dynamic
        "stopCode": stop_id,
        "format": "json"
    }

    url = f"{BASE_URL}/StopMonitoring"

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

            raw_text = response.text.encode().decode("utf-8-sig")
            data = response.json()
            log_debug(f"Raw data received for stop {stop_id}: {str(data)[:300]}...")

    except Exception as e:
        log_debug(f"Error fetching real-time data: {e}")
        return None

    delivery = data.get("ServiceDelivery", {})
    monitoring = delivery.get("StopMonitoringDelivery", [])
    if isinstance(monitoring, list):
        monitoring = monitoring[0] if monitoring else {}

    stops = monitoring.get("MonitoredStopVisit", [])
    if not stops:
        log_debug(f"No real-time buses found for stop {stop_id}")
        return {"inbound": [], "outbound": []}

    inbound = []
    outbound = []
    now = datetime.utcnow()

    for stop in stops:
        journey = stop.get("MonitoredVehicleJourney", {})
        call = journey.get("MonitoredCall", {})
        line_ref = journey.get("LineRef", "")
        destination = journey.get("DestinationName", "Unknown")

        expected = call.get("ExpectedArrivalTime") or call.get("AimedArrivalTime")
        if not expected:
            continue

        try:
            if expected.endswith("Z"):
                arrival = datetime.fromisoformat(expected.replace("Z", "+00:00"))
            else:
                arrival = datetime.fromisoformat(expected)
        except Exception as e:
            log_debug(f"Error parsing arrival time: {e}")
            continue

        if (arrival - now).total_seconds() < -60:
            continue

        status = "On Time"
        display_time = arrival.strftime("%I:%M %p").lstrip("0")

        direction = journey.get("DirectionRef", "0")
        info = {
            "route_number": line_ref.split(":")[-1],
            "destination": destination,
            "arrival_time": display_time,
            "status": status
        }

        if direction == "1":
            inbound.append(info)
        else:
            outbound.append(info)

    return {"inbound": inbound[:3], "outbound": outbound[:3]}
