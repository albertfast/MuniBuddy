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
        self.stops_df = load_stops(self.gtfs_data)
    
    async def get_nearby_stops(self, lat: float, lon: float, radius: float = 0.15):
        log_debug(f"Finding nearby stops for coordinates: ({lat}, {lon}), radius: {radius}")
        stops = await self._load_stops()
        return find_nearby_stops(lat, lon, self.gtfs_data, stops, radius)

    async def get_nearby_buses(self, lat: float, lon: float, radius: float = 0.15):
        log_debug(f"Looking for nearby real-time buses around: ({lat}, {lon}) within {radius} miles")
        nearby_stops = await self.get_nearby_stops(lat, lon, radius)

        results = []
        for stop in nearby_stops:
            stop_id = stop["gtfs_stop_id"]
            realtime_data = await fetch_real_time_stop_data(stop_id)
            results.append({
                "stop_id": stop["stop_id"],
                "stop_name": stop["stop_name"],
                "distance_miles": stop["distance_miles"],
                "buses": realtime_data
            })

        return results

    async def get_stop_schedule(self, stop_id: str):
        log_debug(f"Fetching GTFS schedule for stop ID: {stop_id}")
        return self.scheduler.get_schedule(stop_id)

    # async def get_stop_predictions(self, stop_id: str):
    #     log_debug(f"Fetching real-time predictions for stop ID: {stop_id}")
    #     return await fetch_real_time_stop_data(stop_id)
