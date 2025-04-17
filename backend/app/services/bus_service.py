from app.services.realtime_service import fetch_real_time_stop_data
from app.services.schedule_service import SchedulerService
from app.services.stop_helper import find_nearby_stops
from app.services.debug_logger import log_debug
from app.services.gtfs_service import GTFSService

class BusService:
    def __init__(self, scheduler: SchedulerService):
        log_debug("Initializing BusService...")
        self.scheduler = scheduler

    def get_nearby_stops(self, lat: float, lon: float, radius: float = 0.15, agency: str = "muni"):
        agency = self._normalize_agency(agency)
        log_debug(f"Finding nearby stops for coordinates: ({lat}, {lon}), radius: {radius}, agency: {agency}")

        try:
            stops_df = GTFSService(agency).get_stops()
            if stops_df.empty:
                log_debug(f"✗ No stops found in GTFS DB for agency: {agency}")
                return []

            stops = stops_df.to_dict(orient="records")
            nearby = find_nearby_stops(lat, lon, stops, radius)

            for stop in nearby:
                stop["agency"] = agency

            return nearby
        except Exception as e:
            log_debug(f"[ERROR] Failed to load stops for {agency}: {e}")
            return []

    def get_nearby_buses(self, lat: float, lon: float, radius: float = 0.15, agency: str = "muni"):
        agency = self._normalize_agency(agency)
        log_debug(f"Looking for nearby real-time buses around: ({lat}, {lon}) within {radius} miles for agency: {agency}")

        nearby_stops = self.get_nearby_stops(lat, lon, radius, agency)
        results = []

        for stop in nearby_stops:
            realtime_data = fetch_real_time_stop_data(stop, agency)

            if not realtime_data.get("inbound") and not realtime_data.get("outbound"):
                log_debug(f"No real-time data for stop {stop.get('stop_code')}, trying schedule fallback.")
                realtime_data = self.scheduler.get_schedule(stop["stop_id"], agency)

            for direction in ["inbound", "outbound"]:
                for bus in realtime_data.get(direction, []):
                    results.append({
                        "stop_id": stop["stop_id"],
                        "stop_code": stop.get("stop_code"),
                        "stop_name": stop["stop_name"],
                        "distance_miles": stop["distance_miles"],
                        "direction": direction,
                        "route_number": bus.get("route_number"),
                        "destination": bus.get("destination"),
                        "arrival_time": bus.get("arrival_time"),
                        "status": bus.get("status"),
                        "minutes_until": bus.get("minutes_until", None),
                        "is_realtime": bus.get("is_realtime", False)
                    })

        if not results:
            log_debug("[FALLBACK] No real-time buses found at all. Switching to GTFS schedule for all stops.")
            for stop in nearby_stops:
                schedule = self.scheduler.get_schedule(stop["stop_id"], agency)
                for direction in ["inbound", "outbound"]:
                    for bus in schedule.get(direction, []):
                        results.append({
                            "stop_id": stop["stop_id"],
                            "stop_code": stop.get("stop_code"),
                            "stop_name": stop["stop_name"],
                            "distance_miles": stop["distance_miles"],
                            "direction": direction,
                            "route_number": bus.get("route_number"),
                            "destination": bus.get("destination"),
                            "arrival_time": bus.get("arrival_time"),
                            "status": bus.get("status"),
                            "minutes_until": None,
                            "is_realtime": False
                        })

        return {"buses": results}

    def _normalize_agency(self, agency: str) -> str:
        agency = agency.lower()
        if agency in ["sf", "sfmta", "muni"]:
            return "muni"
        elif agency in ["ba", "bart"]:
            return "bart"
        return agency
