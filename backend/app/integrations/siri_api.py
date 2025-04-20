# app/integrations/siri_api.py
import httpx
import asyncio
from app.config import settings
from app.services.debug_logger import log_debug

def normalize_agency(agency: str) -> str:
    agency = agency.lower()
    if agency in ["sf", "muni", "sfmta"]:
        return "SF"
    elif agency in ["ba", "bart"]:
        return "BA"
    return agency.upper()

async def fetch_siri_data_multi(stop_codes: list[str], agency: str) -> dict:
    agency_code = normalize_agency(agency)
    url = f"{settings.TRANSIT_511_BASE_URL}/StopMonitoring"

    results = {}

    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = []
        for stop_code in stop_codes:
            params = {
                "api_key": settings.API_KEY,
                "agency": agency_code,
                "stopCode": stop_code,
                "format": "json"
            }
            tasks.append(client.get(url, params=params))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for stop_code, resp in zip(stop_codes, responses):
            if isinstance(resp, Exception):
                log_debug(f"[SIRI MULTI] ❌ Error for stop {stop_code}: {resp}")
                results[stop_code] = {"error": str(resp)}
            else:
                try:
                    results[stop_code] = resp.json()
                except Exception as e:
                    log_debug(f"[SIRI MULTI] ❌ JSON parse failed for {stop_code}: {e}")
                    results[stop_code] = {"error": "Invalid JSON"}

    return results
