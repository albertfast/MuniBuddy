from typing import List, Dict, Any
from app.config import settings
from app.services.stop_helper import load_stops, find_nearby_stops
from app.services.schedule_service import SchedulerService
from app.services.realtime_bart_service import RealtimeBartService
from app.services.debug_logger import log_debug
from app.integrations.siri_api import fetch_siri_data, fetch_siri_data_multi

class BartService:
    def __init__(self, scheduler: SchedulerService):
        self.scheduler = scheduler
        self.agency = settings.normalize_agency("bart")
        self.realtime = RealtimeBartService(self.scheduler)

    def get_bart_stop_details(self, stop_id: str) -> Dict[str, Any]:
        try:
            stops = load_stops(self.agency)
            for stop in stops:
                if stop["stop_id"] == stop_id or stop.get("stop_code") == stop_id:
                    return {
                        "stop_id": stop["stop_id"],
                        "stop_code": stop.get("stop_code"),
                        "stop_name": stop["stop_name"],
                        "stop_lat": stop["stop_lat"],
                        "stop_lon": stop["stop_lon"],
                        "agency": self.agency
                    }
            return {"stop_id": stop_id, "stop_name": "Unknown Stop", "agency": self.agency}
        except Exception as e:
            log_debug(f"[BART:get_bart_stop_details] Error: {e}")
            return {"stop_id": stop_id, "stop_name": "Lookup Failed", "agency": self.agency}

    async def get_real_time_arrivals(self, lat: float, lon: float, radius: float = 0.15, agency: str = "bart"):
        agency = settings.normalize_agency(agency)
        log_debug(f"[BART] Looking for nearby real-time trains at ({lat}, {lon}) within {radius} miles")

        stops = load_stops(agency)
        nearby_stops = find_nearby_stops(lat, lon, stops, radius)
        stop_code_map = {stop["stop_code"] or stop["stop_id"]: stop for stop in nearby_stops}

        stop_codes = list(stop_code_map.keys())
        if not stop_codes:
            log_debug("[BART] ❌ No nearby stop codes found.")
            return {"inbound": [], "outbound": []}

        raw_data = await fetch_siri_data_multi(stop_codes, agency)
        results = []

        for stop_code, data in raw_data.items():
            stop_info = stop_code_map.get(stop_code)
            visits = data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", {}).get("MonitoredStopVisit", [])
            for visit in visits:
                journey = visit.get("MonitoredVehicleJourney", {})
                call = journey.get("MonitoredCall", {})
                arrival_time = call.get("ExpectedArrivalTime") or call.get("AimedArrivalTime")

                results.append({
                    "stop_id": stop_info.get("stop_id"),
                    "stop_code": stop_code,
                    "stop_name": stop_info.get("stop_name"),
                    "distance_miles": stop_info.get("distance_miles"),
                    "direction": journey.get("DirectionRef", "").lower(),
                    "route_number": journey.get("PublishedLineName"),
                    "destination": journey.get("DestinationName"),
                    "arrival_time": arrival_time,
                    "status": "Due",  # optionally calculate min_until
                    "minutes_until": None,
                    "is_realtime": True,
                    "vehicle": {
                        "lat": journey.get("VehicleLocation", {}).get("Latitude", ""),
                        "lon": journey.get("VehicleLocation", {}).get("Longitude", "")
                    }
                })

        return {
            "inbound": [r for r in results if r["direction"] in ["ib", "inbound", "n"]],
            "outbound": [r for r in results if r["direction"] in ["ob", "outbound", "s"]]
        }


    def get_stop_predictions(self, stop_id: str, lat: float = None, lon: float = None) -> Dict[str, Any]:
        try:
            realtime = self.realtime.fetch_real_time_stop_data(stop_id)
            if not realtime.get("inbound") and not realtime.get("outbound"):
                fallback = self.scheduler.get_schedule(stop_id, agency="bart")
                return fallback

            for entry in realtime.get("inbound", []) + realtime.get("outbound", []):
                entry.setdefault("vehicle", {"lat": "", "lon": ""})

            return realtime

        except Exception as e:
            log_debug(f"[BART PREDICTIONS] Error fetching predictions for {stop_id}: {e}")
            return {"inbound": [], "outbound": []}
