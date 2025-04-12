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
        return find_nearby_stops(lat, lon, stops, radius)

    def get_nearby_buses(self, lat: float, lon: float, radius: float = 0.15, agency: str = "muni"):
        log_debug(f"Looking for nearby real-time buses around: ({lat}, {lon}) within {radius} miles for agency: {agency}")
        
        nearby_stops = self.get_nearby_stops(lat, lon, radius, agency)

        results = []
        for stop in nearby_stops:
            
            stop_id = stop.get("gtfs_stop_id", stop["stop_id"])
            if agency == "muni" and not str(stop_id).startswith("1"):
                stop_id = f"1{stop_id}"

            realtime_data = fetch_real_time_stop_data(stop_id, agency)

            results.append({
                "stop_id": stop["stop_id"],
                "stop_name": stop["stop_name"],
                "distance_miles": stop["distance_miles"],
                "buses": realtime_data
            })

        return {"stops": results}