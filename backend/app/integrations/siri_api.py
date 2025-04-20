import httpx
from app.services.debug_logger import log_debug
from app.config import settings

def normalize_agency(agency: str) -> str:
    """
    Normalize agency to 511-compatible format.
    """
    agency = agency.lower()
    if agency in ["sf", "muni", "sfmta"]:
        return "SF"
    elif agency in ["ba", "bart"]:
        return "BA"
    return agency.upper()

def fetch_siri_data(stop_code: str, agency: str = "SF") -> dict:
    """
    Fetch StopMonitoring data from 511 SIRI API.
    Returns full JSON response or error information.
    """
    agency = normalize_agency(agency)
    url = f"{settings.TRANSIT_511_BASE_URL}/StopMonitoring"
    params = {
        "api_key": settings.API_KEY,
        "agency": agency,
        "stopCode": stop_code,
        "format": "json"
    }

    try:
        with httpx.AsyncClient(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Basic structure validation
            delivery = data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", [])
            if not delivery:
                log_debug(f"[SIRI API] ⚠️ No StopMonitoringDelivery for stop_code={stop_code}, agency={agency}")
            else:
                log_debug(f"[SIRI API] ✅ Received real-time data for stop_code={stop_code}, agency={agency}")
            
            return data

    except httpx.HTTPStatusError as e:
        log_debug(f"[SIRI API] ❌ HTTP {e.response.status_code} for {stop_code} ({agency})")
        return {"error": f"HTTP error {e.response.status_code}", "details": str(e)}
    except httpx.RequestError as e:
        log_debug(f"[SIRI API] ❌ Request failed: {e}")
        return {"error": "Request error", "details": str(e)}
    except Exception as e:
        log_debug(f"[SIRI API] ❌ Unexpected error: {e}")
        return {"error": "Unexpected error", "details": str(e)}
