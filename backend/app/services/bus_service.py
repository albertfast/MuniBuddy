from app.services.realtime_service import fetch_real_time_stop_data
from app.services.schedule_service import SchedulerService
from app.services.gtfs_service import GTFSService
from app.services.debug_logger import log_debug
from math import radians, cos, sin, asin, sqrt
import pandas as pd

class BusService:
    def __init__(self, scheduler: SchedulerService):
        log_debug("Initializing BusService...")
        self.scheduler = scheduler

    def _normalize_agency(self, agency: str) -> str:
        agency = agency.lower()
        if agency in ["sf", "sfmta", "muni"]:
            return "muni"
        elif agency in ["ba", "bart"]:
            return "bart"
        return agency

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 3956
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
        return R * 2 * asin(sqrt(a))

    def get_nearby_stops(self, lat: float, lon: float, radius: float = 0.15, agency: str = "muni"):
        agency = self._normalize_agency(agency)
        log_debug(f"Finding nearby stops for coordinates: ({lat}, {lon}), radius: {radius}, agency: {agency}")

        gtfs = GTFSService(agency)
        stops_df = gtfs.get_stops()

        if stops_df.empty:
            log_debug(f"✗ No GTFS stops found for agency: {agency}")
            return []

        stops_df["stop_lat"] = pd.to_numeric(stops_df["stop_lat"], errors="coerce")
        stops_df["stop_lon"] = pd.to_numeric(stops_df["stop_lon"], errors="coerce")
        stops_df["distance_miles"] = stops_df.apply(
            lambda row: self._haversine(lat, lon, row["stop_lat"], row["stop_lon"]), axis=1
        )

        nearby = stops_df[stops_df["distance_miles"] <= radius].copy()
        records = nearby.sort_values("distance_miles").to_dict(orient="records")
        for stop in records:
            stop["agency"] = agency
        return records

    def get_nearby_buses(self, lat: float, lon: float, radius: float = 0.15, agency: str = "muni"):
        agency = self._normalize_agency(agency)
        log_debug(f"Looking for nearby real-time buses around: ({lat}, {lon}) within {radius} miles for agency: {agency}")

        nearby_stops = self.get_nearby_stops(lat, lon, radius, agency)
        results = []

        for stop in nearby_stops:
            realtime_data = fetch_real_time_stop_data(stop, agency)

            if not realtime_data.get("inbound") and not realtime_data.get("outbound"):
                log_debug(f"No real-time data for stop {stop['stop_code']}, using static schedule...")
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
            log_debug(f"[FALLBACK] No buses found. Using GTFS schedule as fallback.")
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
