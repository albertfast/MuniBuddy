from typing import List, Dict, Any, Optional
from app.config import settings
from app.services.stop_helper import load_stops, find_nearby_stops
from app.services.schedule_service import SchedulerService
from app.services.realtime_bart_service import RealtimeBartService
from app.services.debug_logger import log_debug
from app.integrations.siri_api import fetch_siri_data, fetch_siri_data_multi
import httpx
class BartService:
    def __init__(self, scheduler: SchedulerService):
        self.scheduler = scheduler
        self.agency = settings.normalize_agency("bart")
        self.realtime = RealtimeBartService(self.scheduler)

    def get_nearby_stops(
        self,
        lat: float,
        lon: float,
        radius: float = 0.15,
        agency: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Return nearby stops for given agency (or all if agency=None)"""
        normalized_agency = settings.normalize_agency(agency) if agency else None
        stops = load_stops(normalized_agency)
        return find_nearby_stops(lat, lon, stops, radius, limit)

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

    async def get_real_time_arrival_by_stop(self, stop_code: str, agency: str = "bart") -> Dict[str, Any]:
        raw_data = await fetch_siri_data_multi([stop_code], agency)
        normalized_keys = {k.lower(): v for k, v in raw_data.items()}
        siri_data = normalized_keys.get(stop_code.lower(), {})
        visits = siri_data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", [{}])[0].get("MonitoredStopVisit", [])

        parsed = {"inbound": [], "outbound": []}

        # Debugging: verify stop resolution
        stops = load_stops(settings.normalize_agency(agency))
        debug_matches = [s for s in stops if stop_code.lower() in (s["stop_id"].lower(), s["stop_code"].lower())]
        print(f"[DEBUG] Matching stops for code {stop_code}: {debug_matches}")

        for visit in visits:
            journey = visit.get("MonitoredVehicleJourney", {})
            call = journey.get("MonitoredCall", {})
            arrival_time = call.get("ExpectedArrivalTime") or call.get("AimedArrivalTime")
            direction = journey.get("DirectionRef", "").strip().lower()

            entry = {
                "stop_id": stop_info.get("stop_id"),
                "stop_code": stop_code,
                "stop_name": stop_info.get("stop_name"),
                "route_number": journey.get("PublishedLineName"),
                "destination": journey.get("DestinationName"),
                "arrival_time": arrival_time,
                "status": "Due",
                "minutes_until": None,
                "is_realtime": True,
                "vehicle": {
                    "lat": journey.get("VehicleLocation", {}).get("Latitude", ""),
                    "lon": journey.get("VehicleLocation", {}).get("Longitude", "")
                }
            }

            if direction in ["ib", "n"]:
                parsed["inbound"].append(entry)
            elif direction in ["ob", "s"]:
                parsed["outbound"].append(entry)
            else:
                parsed["outbound"].append(entry)  # default fallback

        return parsed




    # def get_stop_predictions(self, stop_id: str, lat: float = None, lon: float = None) -> Dict[str, Any]:
    #     try:
    #         realtime = self.realtime.fetch_real_time_stop_data(stop_id)
    #         if not realtime.get("inbound") and not realtime.get("outbound"):
    #             fallback = self.scheduler.get_schedule(stop_id, agency="bart")
    #             return fallback

    #         for entry in realtime.get("inbound", []) + realtime.get("outbound", []):
    #             entry.setdefault("vehicle", {"lat": "", "lon": ""})

    #         return realtime

    #     except Exception as e:
    #         log_debug(f"[BART PREDICTIONS] Error fetching predictions for {stop_id}: {e}")
    #         return {"inbound": [], "outbound": []}


