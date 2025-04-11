from app.services.realtime_service import fetch_stop_data
from app.services.schedule_service import get_static_schedule
from app.services.stop_helper import calculate_distance, load_stops, find_nearby_stops
from app.services.debug_logger import log_debug
from app.config import settings
import pandas as pd

class BusService:
    def __init__(self):
        log_debug("Initializing BusService...")
        self.gtfs_data = settings.get_gtfs_data("muni")
        self.stops_df = load_stops(self.gtfs_data, "muni")

    async def get_nearby_buses(self, lat: float, lon: float, radius: float = 0.15):
        log_debug(f"Finding nearby buses for coordinates: ({lat}, {lon}), radius: {radius}")
        nearby_stops = find_nearby_stops(lat, lon, radius, self.stops_df)
        stop_ids = [stop['stop_id'] for stop in nearby_stops]
        log_debug(f"Found {len(stop_ids)} nearby stops.")
        return {"nearby_stop_ids": stop_ids, "stops": nearby_stops}

    async def get_stop_schedule(self, stop_id: str):
        log_debug(f"Fetching GTFS schedule for stop ID: {stop_id}")
        return get_static_schedule(stop_id, self.gtfs_data)

    async def get_stop_predictions(self, stop_id: str):
        log_debug(f"Fetching real-time predictions for stop ID: {stop_id}")
        return await fetch_stop_data(stop_id)
