import httpx
from typing import List, Dict
from app.config import settings

async def fetch_vehicle_locations_by_refs(vehicle_refs: List[str], agency: str = "bart") -> List[Dict]:
    norm_agency = settings.normalize_agency(agency, to_511=True)
    url = f"{settings.TRANSIT_511_BASE_URL}/VehicleMonitoring"

    matched = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for vref in vehicle_refs[:10]:
            params = {
                "api_key": settings.API_KEY,
                "agency": norm_agency,
                "vehicleRef": vref,
                "format": "json"
            }
            try:
                res = await client.get(url, params=params)
                data = res.json()
                activities = data.get("ServiceDelivery", {}).get("VehicleMonitoringDelivery", [{}])[0].get("VehicleActivity", [])
                for act in activities:
                    mvj = act.get("MonitoredVehicleJourney", {})
                    loc = mvj.get("VehicleLocation", {})
                    matched.append({
                        "vehicle_id": mvj.get("VehicleRef"),
                        "line": mvj.get("LineRef"),
                        "latitude": loc.get("Latitude"),
                        "longitude": loc.get("Longitude")
                    })
            except Exception as e:
                print(f"[WARN] Failed to fetch location for vehicle {vref}: {e}")
    return matched
