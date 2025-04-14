from typing import List, Dict, Any
from app.config import settings
from app.services.stop_helper import load_stops, find_nearby_stops
from app.services.fetch_real_time_stop_data import RealtimeBartService
from app.services.debug_logger import log_debug

class BartService:
    def __init__(self):
        self.agency = "bart"
        self.realtime = RealtimeBartService()

    async def get_nearby_stops_with_arrivals(self, lat: float, lon: float, radius: float = 0.15) -> List[Dict[str, Any]]:
        log_debug(f"[BART] Getting nearby stops with real-time arrivals around ({lat}, {lon}) within {radius} miles.")
        stops = load_stops(self.agency)
        nearby = find_nearby_stops(lat, lon, stops, radius)
        enriched = []

        for stop in nearby:
            arrivals = await self.realtime.fetch_if_bart_stop_nearby(stop["stop_id"], lat, lon, radius)
            stop["arrivals"] = arrivals
            stop["agency"] = self.agency
            enriched.append(stop)

        return enriched

    def get_nearby_stops(self, lat: float, lon: float, radius: float = 0.15, agency: str = "bart") -> List[Dict[str, Any]]:
        log_debug(f"[BART] Finding nearby stops for coordinates: ({lat}, {lon}), radius: {radius}, agency: {agency}")
        stops = load_stops(agency)
        nearby = find_nearby_stops(lat, lon, stops, radius)
        for stop in nearby:
            stop["agency"] = agency
        return nearby

    async def get_real_time_arrivals(self, stop_id: str, lat: float = None, lon: float = None, radius: float = 0.15) -> Dict[str, Any]:
        log_debug(f"[BART] Getting real-time arrivals for stop_id: {stop_id}")
        if lat is not None and lon is not None:
            return await self.realtime.fetch_if_bart_stop_nearby(stop_id, lat, lon, radius)
        return await self.realtime.fetch_if_bart_stop_nearby(stop_id, 0, 0, 0)

    def get_route_stops(self, route_id: str, direction_id: int = 0) -> List[Dict[str, Any]]:
        try:
            gtfs_data = settings.get_gtfs_data(self.agency)
            stop_times_df = gtfs_data.get("stop_times")
            trips_df = gtfs_data.get("trips")
            stops_df = gtfs_data.get("stops")

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
                        "stop_lon": stop.get("stop_lon"),
                        "agency": self.agency
                    })

            return route_stops

        except Exception as e:
            log_debug(f"[BART] Error fetching route stops: {e}")
            return []
    
     async def fetch_if_bart_stop_nearby(self, stop_id: str, lat: float, lon: float, radius: float = 0.15) -> Dict[str, Any]:
        stops = load_stops(self.agency)
        nearby = find_nearby_stops(lat, lon, stops, radius)
        if not nearby:
            log_debug(f"[RealtimeBART] No nearby BART stops for location ({lat}, {lon}) - Skipping real-time fetch")
            return {"inbound": [], "outbound": []}

        log_debug(f"[RealtimeBART] Nearby BART stops found for location ({lat}, {lon}) - Fetching real-time data for stop {stop_id}")
        realtime_data = await fetch_real_time_stop_data(stop_id, agency=self.agency)

        gtfs_data = settings.get_gtfs_data(self.agency)
        if not isinstance(gtfs_data, dict):
            log_debug("[BART] Error: GTFS data not properly loaded for BART")
            return realtime_data

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

    async def get_bart_511_raw_data(self, stop_code: str) -> Dict[str, Any]:
        log_debug(f"[RealtimeBART] Requesting raw 511 data for stop_code={stop_code}")
        return await fetch_real_time_stop_data(stop_code, agency=self.agency, raw=True)


bart_service = BartService()
