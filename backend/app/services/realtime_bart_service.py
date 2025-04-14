from typing import Dict, Any
from app.services.stop_helper import load_stops, find_nearby_stops
from app.services.realtime_service import fetch_real_time_stop_data
from app.services.debug_logger import log_debug
from app.config import settings

class RealtimeBartService:
    def __init__(self):
        self.agency = "bart"

    async def fetch_if_bart_stop_nearby(self, stop_id: str, lat: float, lon: float, radius: float = 0.15) -> Dict[str, Any]:
        stops = load_stops(self.agency)
        nearby = find_nearby_stops(lat, lon, stops, radius)
        if not nearby:
            log_debug(f"[RealtimeBART] No nearby BART stops for location ({lat}, {lon}) - Skipping real-time fetch")
            return {"inbound": [], "outbound": []}

        log_debug(f"[RealtimeBART] Nearby BART stops found for location ({lat}, {lon}) - Fetching real-time data for stop {stop_id}")
        realtime_data = await fetch_real_time_stop_data(stop_id, agency=self.agency)

        # Enrich with route_id, direction label, and estimated arrival info
        gtfs_data = settings.get_gtfs_data(self.agency)
        trips_df = gtfs_data.get("trips")
        routes_df = gtfs_data.get("routes")
        directions_df = gtfs_data.get("directions")

        for direction_key in ["inbound", "outbound"]:
            enriched = []
            for bus in realtime_data.get(direction_key, []):
                route_number = bus.get("route_number")
                destination = bus.get("destination")
                route_row = routes_df[routes_df["route_short_name"] == route_number]

                if not route_row.empty:
                    route_id = route_row.iloc[0]["route_id"]
                    trip_rows = trips_df[(trips_df["route_id"] == route_id) & (trips_df["trip_headsign"] == destination)]

                    if not trip_rows.empty:
                        direction_id = trip_rows.iloc[0]["direction_id"]
                        direction_label = "Outbound"
                        match = directions_df[(directions_df["route_id"] == route_id) & (directions_df["direction_id"] == direction_id)]
                        if not match.empty:
                            direction_label = match.iloc[0]["direction"]

                        enriched.append({
                            **bus,
                            "route_id": route_id,
                            "direction_id": direction_id,
                            "direction": direction_label
                        })
                    else:
                        enriched.append(bus)
                else:
                    enriched.append(bus)

            realtime_data[direction_key] = enriched

        return realtime_data
