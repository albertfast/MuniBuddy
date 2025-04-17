from typing import List, Dict, Any
from app.config import settings
from app.services.stop_helper import load_stops, find_nearby_stops
from app.services.schedule_service import SchedulerService
from app.services.realtime_bart_service import RealtimeBartService
from app.services.debug_logger import log_debug
from app.integrations.siri_api import fetch_siri_data

class BartService:
    def __init__(self):
        self.agency = settings.normalize_agency("bart")
        self.realtime = RealtimeBartService()
        self.scheduler = SchedulerService()

    def get_nearby_stops(self, lat: float, lon: float, radius: float = 0.15) -> List[Dict]:
        log_debug(f"[BART:Realtime] Finding nearby stops for ({lat}, {lon}) radius={radius}")
        try:
            stops = load_stops(self.agency)
            if not stops:
                log_debug("[BART:Realtime] ✗ No BART stops loaded.")
                return []
            nearby = find_nearby_stops(lat, lon, stops, radius)
            for stop in nearby:
                stop["agency"] = self.agency
            return nearby
        except Exception as e:
            log_debug(f"[BART:Realtime] Error in get_nearby_stops: {e}")
            return []


    async def get_nearby_stops_with_arrivals(self, lat: float, lon: float, radius: float = 0.15) -> List[Dict[str, Any]]:
        log_debug(f"[BART] Getting nearby stops with real-time arrivals around ({lat}, {lon}) within {radius} miles.")
        stops = self.get_nearby_stops(lat, lon, radius)
        enriched = []

        for stop in stops:
            arrivals = await self.realtime.fetch_real_time_stop_data(stop["stop_code"], lat, lon, radius)
            stop["arrivals"] = arrivals
            stop["agency"] = self.agency
            enriched.append(stop)

        return enriched

    async def get_real_time_arrivals(self, stop_code: str, lat: float = None, lon: float = None, radius: float = 0.15) -> Dict[str, Any]:
        log_debug(f"[BART] Getting real-time arrivals for stop_code: {stop_code}")
        try:
            realtime = await self.realtime.fetch_real_time_stop_data(stop_code, lat, lon, radius)

            if not realtime.get("inbound") and not realtime.get("outbound"):
                log_debug(f"[BART] No realtime data for {stop_code}, using GTFS fallback")
                return self.scheduler.get_schedule(stop_code, agency=self.agency)

            return realtime

        except Exception as e:
            log_debug(f"[BART] Error fetching arrivals: {e}")
            return {"inbound": [], "outbound": []}

    async def get_bart_511_raw_data(self, stop_code: str) -> Dict[str, Any]:
        log_debug(f"[BART] Requesting raw 511 data for stop_code={stop_code}")
        return await self.realtime.get_bart_511_raw_data(stop_code)

    def get_siri_raw_data(self, stop_code: str) -> Dict[str, Any]:
        try:
            return fetch_siri_data(stop_code, agency=self.agency)
        except Exception as e:
            log_debug(f"[BART] Error fetching Siri data for stop_code={stop_code}: {e}")
            return {"error": str(e)}

    async def get_bart_stop_details(self, stop_id: str) -> Dict[str, Any]:
        return await self.realtime.get_bart_stop_details(stop_id)

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
            ordered_stop_codes = (
                filtered_stop_times.sort_values("stop_sequence")["stop_code"]
                .drop_duplicates()
                .tolist()
            )

            stop_lookup = stops_df.set_index("stop_code").to_dict("index")
            route_stops = []
            for stop_code in ordered_stop_codes:
                stop = stop_lookup.get(stop_code)
                if stop:
                    route_stops.append({
                        "stop_code": stop_code,
                        "stop_name": stop.get("stop_name"),
                        "stop_lat": stop.get("stop_lat"),
                        "stop_lon": stop.get("stop_lon"),
                        "agency": self.agency
                    })

            return route_stops

        except Exception as e:
            log_debug(f"[BART] Error fetching route stops: {e}")
            return []

bart_service = BartService()
