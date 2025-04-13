from typing import List, Dict, Any
from app.config import settings
from app.services.stop_helper import load_stops, find_nearby_stops
from app.services.realtime_service import fetch_real_time_stop_data
from app.services.debug_logger import log_debug

class BartService:
    def __init__(self):
        self.agency = "bart"
        self.gtfs_data = settings.get_gtfs_data(self.agency)

    def get_nearby_stops(self, lat: float, lon: float, radius: float = 0.15) -> List[Dict[str, Any]]:
        log_debug(f"[BART] Looking for nearby stops around ({lat}, {lon}) within {radius} miles.")
        stops = load_stops(self.agency)
        return find_nearby_stops(lat, lon, stops, radius)

    def get_real_time_arrivals(self, stop_id: str) -> Dict[str, Any]:
        log_debug(f"[BART] Getting real-time arrivals for stop_id: {stop_id}")
        return fetch_real_time_stop_data(stop_id, agency=self.agency)

    def get_route_stops(self, route_id: str, direction_id: int = 0) -> List[Dict[str, Any]]:
        try:
            stop_times_df = self.gtfs_data.get("stop_times")
            trips_df = self.gtfs_data.get("trips")
            stops_df = self.gtfs_data.get("stops")

            trip_ids = trips_df[
                (trips_df["route_id"] == route_id) &
                (trips_df["direction_id"] == direction_id)
            ]["trip_id"].unique()

            filtered_stop_times = stop_times_df[stop_times_df["trip_id"].isin(trip_ids)]

            ordered_stop_ids = (
                filtered_stop_times.sort_values("stop_sequence")["stop_id"]
                .drop_duplicates()
                .tolist()
            )

            stop_lookup = stops_df.set_index("stop_id").to_dict("index")

            route_stops = []
            for stop_id in ordered_stop_ids:
                stop = stop_lookup.get(stop_id)
                if stop:
                    route_stops.append({
                        "stop_id": stop_id,
                        "stop_name": stop.get("stop_name"),
                        "stop_lat": stop.get("stop_lat"),
                        "stop_lon": stop.get("stop_lon")
                    })

            return route_stops

        except Exception as e:
            log_debug(f"[BART] Error fetching route stops: {e}")
            return []
