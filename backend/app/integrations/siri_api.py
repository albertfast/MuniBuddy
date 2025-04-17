import httpx
import os
from app.services.debug_logger import log_debug

API_KEY = os.getenv("API_KEY", "your-511-key")
TRANSIT_511_BASE_URL = os.getenv("TRANSIT_511_BASE_URL", "http://api.511.org/transit")

def normalize_agency(agency: str) -> str:
    agency = agency.lower()
    if agency in ["sf", "muni", "sfmta"]:
        return "SF"
    elif agency in ["ba", "bart"]:
        return "BA"
    return agency.upper()

async def fetch_siri_data(stop_code: str, agency: str = "SF") -> dict:
    agency = normalize_agency(agency)
    url = f"{TRANSIT_511_BASE_URL}/StopMonitoring"
    params = {
        "api_key": API_KEY,
        "agency": agency,
        "stopCode": stop_code,
        "format": "json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Debug: basic structure check
            delivery = data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", [])
            if not delivery:
                log_debug(f"[SIRI API] No StopMonitoringDelivery data for stop_code={stop_code}, agency={agency}")
            else:
                log_debug(f"[SIRI API] Received real-time data for stop_code={stop_code}, agency={agency}")

            return data

    except httpx.HTTPStatusError as e:
        log_debug(f"[SIRI API] HTTP error {e.response.status_code} for stop_code={stop_code}, agency={agency}")
        return {"error": f"HTTP error: {e.response.status_code}", "details": str(e)}
    except httpx.RequestError as e:
        log_debug(f"[SIRI API] Request failed: {e}")
        return {"error": "Request error", "details": str(e)}
    except Exception as e:
        log_debug(f"[SIRI API] Unexpected error: {e}")
        return {"error": "Unexpected error", "details": str(e)}
