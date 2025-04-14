from app.services.realtime_service import fetch_real_time_stop_data
from app.services.schedule_service import SchedulerService
from app.services.stop_helper import load_stops, find_nearby_stops
from app.services.debug_logger import log_debug
from app.config import settings

class BusService:
    def __init__(self, scheduler: SchedulerService):
        log_debug("Initializing BusService...")
        self.scheduler = scheduler
        self.gtfs_data = settings.get_gtfs_data("muni")

    def get_nearby_stops(self, lat: float, lon: float, radius: float = 0.15, agency: str = "muni"):
        log_debug(f"Finding nearby stops for coordinates: ({lat}, {lon}), radius: {radius}, agency: {agency}")
        
        gtfs_data = settings.get_gtfs_data(agency)
        if not gtfs_data:
            log_debug(f"✗ No GTFS data found for agency: {agency}")
            return []

        stops = load_stops(agency)
        nearby = find_nearby_stops(lat, lon, stops, radius)

        for stop in nearby:
            stop["agency"] = agency

        return nearby

    def get_nearby_buses(self, lat: float, lon: float, radius: float = 0.15, agency: str = "muni"):
        log_debug(f"Looking for nearby real-time buses around: ({lat}, {lon}) within {radius} miles for agency: {agency}")

        nearby_stops = self.get_nearby_stops(lat, lon, radius, agency)
        results = []

        for stop in nearby_stops:

            realtime_data = fetch_real_time_stop_data(stop, agency)

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
                        "minutes_until": bus.get("minutes_until"),
                        "is_realtime": bus.get("is_realtime")
                    })

        return {"buses": results}