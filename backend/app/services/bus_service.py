from typing import List, Dict, Any, Optional
from app.config import settings
from app.services.stop_helper import load_stops, find_nearby_stops
from app.services.schedule_service import SchedulerService
from app.services.realtime_service import fetch_real_time_stop_data
from app.services.debug_logger import log_debug


class BusService:
    def __init__(self, scheduler: SchedulerService):
        self.scheduler = scheduler

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

    def get_nearby_buses(
        self,
        lat: float,
        lon: float,
        radius: float = 0.15,
        agency: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return real-time and fallback GTFS schedule for nearby stops."""
        normalized_agency = settings.normalize_agency(agency) if agency else None
        log_debug(f"[BusService] Looking for nearby buses at ({lat}, {lon}) agency={normalized_agency or 'ALL'}")

        nearby_stops = self.get_nearby_stops(lat, lon, radius, normalized_agency)
        results = []

        for stop in nearby_stops:
            stop_id = stop["stop_id"]
            stop_code = stop.get("stop_code")
            agency_for_stop = stop["agency"]

            realtime_data = fetch_real_time_stop_data(stop_id, agency=agency_for_stop)

            # fallback if real-time empty
            if not realtime_data.get("inbound") and not realtime_data.get("outbound"):
                log_debug(f"No real-time data for {stop_id}, using schedule fallback")
                realtime_data = self.scheduler.get_schedule(stop_id, agency=agency_for_stop)

            for direction in ["inbound", "outbound"]:
                for bus in realtime_data.get(direction, []):
                    results.append({
                        "stop_id": stop_id,
                        "stop_code": stop_code,
                        "stop_name": stop["stop_name"],
                        "distance_miles": stop["distance_miles"],
                        "direction": direction,
                        "route_number": bus.get("route_number"),
                        "destination": bus.get("destination"),
                        "arrival_time": bus.get("arrival_time"),
                        "status": bus.get("status"),
                        "minutes_until": bus.get("minutes_until", None),
                        "is_realtime": bus.get("is_realtime", False),
                        "vehicle": bus.get("vehicle", {"lat": "", "lon": ""})
                    })

        if not results:
            log_debug("[Fallback] No real-time or schedule data available")
        return {"buses": results}
