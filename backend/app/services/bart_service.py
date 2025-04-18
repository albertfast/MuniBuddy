from typing import List, Dict, Any, Optional
from app.services.realtime_service import fetch_real_time_stop_data
from app.services.schedule_service import SchedulerService
from app.services.stop_helper import load_stops, find_nearby_stops
from app.services.debug_logger import log_debug
from app.config import settings

class BartService:
    def __init__(self, scheduler: SchedulerService):
        log_debug("Initializing BartService...")
        self.scheduler = scheduler

    def get_nearby_barts(self, lat: float, lon: float, radius: float = 0.15, agency: str = "bart"):
        agency = settings.normalize_agency(agency)
        log_debug(f"[BART] Finding nearby stops for coordinates: ({lat}, {lon}), radius: {radius}, agency: {agency}")
        try:
            stops = load_stops(agency)
            if not stops:
                return []
            return find_nearby_stops(lat, lon, stops, radius)
        except Exception as e:
            log_debug(f"[BART ERROR] get_nearby_barts failed for {agency}: {e}")
            return []

    def get_nearby_trains(self, lat: float, lon: float, radius: float = 0.15, agency: str = "bart"):
        agency = settings.normalize_agency(agency)
        log_debug(f"[BART] Looking for nearby real-time trains at ({lat}, {lon}) within {radius} miles")
        nearby_stops = self.get_nearby_barts(lat, lon, radius, agency)
        results = []

        for stop in nearby_stops:
            realtime_data = fetch_real_time_stop_data(stop["stop_id"], agency)

            if not realtime_data.get("inbound") and not realtime_data.get("outbound"):
                log_debug(f"[BART FALLBACK] No live data for stop {stop['stop_id']}, using GTFS fallback")
                realtime_data = self.scheduler.get_schedule(stop["stop_id"], agency)

            for direction in ["inbound", "outbound"]:
                for train in realtime_data.get(direction, []):
                    results.append({
                        "stop_id": stop["stop_id"],
                        "stop_code": stop.get("stop_code"),
                        "stop_name": stop["stop_name"],
                        "distance_miles": stop["distance_miles"],
                        "direction": direction,
                        "route_number": train.get("route_number"),
                        "destination": train.get("destination"),
                        "arrival_time": train.get("arrival_time"),
                        "status": train.get("status"),
                        "minutes_until": train.get("minutes_until", None),
                        "is_realtime": train.get("is_realtime", False),
                        "vehicle": train.get("vehicle", {"lat": "", "lon": ""})
                    })

        return {"trains": results}

    async def get_stop_predictions(self, stop_id: str, lat: float = None, lon: float = None) -> Dict[str, Any]:
        try:
            realtime = await fetch_real_time_stop_data(stop_id, agency="bart")
            if not realtime.get("inbound") and not realtime.get("outbound"):
                fallback = self.scheduler.get_schedule(stop_id, agency="bart")
                return fallback

            for entry in realtime.get("inbound", []) + realtime.get("outbound", []):
                entry.setdefault("vehicle", {"lat": "", "lon": ""})

            return realtime

        except Exception as e:
            log_debug(f"[BART PREDICTIONS] Error fetching predictions for {stop_id}: {e}")
            return {"inbound": [], "outbound": []}