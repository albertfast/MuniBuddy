from typing import Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from app.services.gtfs_service import GTFSService
from app.services.debug_logger import log_debug

class SchedulerService:
    def __init__(self):
        self.services = {
            "muni": GTFSService("muni"),
            "bart": GTFSService("bart")
        }

    def get_schedule(self, stop_id: str, agency: str = "muni") -> Dict[str, Any]:
        agency = agency.lower()
        log_debug(f"[SchedulerService] Looking up schedule for stop: {stop_id}, agency: {agency}")

        service = self.services.get(agency)
        if not service:
            log_debug(f"Unsupported agency: {agency}")
            return {"inbound": [], "outbound": []}

        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        weekday = now.strftime("%A").lower()

        try:
            stop_times = service._query("stop_times", "stop_id = :stop_id", {"stop_id": stop_id})
            if stop_times.empty:
                return {"inbound": [], "outbound": []}

            calendar = service.get_calendar()
            routes = service.get_routes()
            trips = service._query("trips")

            active_services = calendar[
                (calendar[weekday] == 1) &
                (pd.to_numeric(calendar["start_date"]) <= int(now.strftime("%Y%m%d"))) &
                (pd.to_numeric(calendar["end_date"]) >= int(now.strftime("%Y%m%d")))
            ]["service_id"].tolist()

            active_trips = trips[trips["service_id"].isin(active_services)]

            merged = (
                stop_times
                .merge(active_trips[["trip_id", "route_id", "direction_id", "trip_headsign"]], on="trip_id")
                .merge(routes[["route_id", "route_short_name", "route_long_name"]], on="route_id")
            )

            future = []
            for _, row in merged.iterrows():
                try:
                    h, m, s = map(int, row["arrival_time"].split(":"))
                    arrival = datetime(now.year, now.month, now.day, h % 24, m, s)
                    if h >= 24:
                        arrival += timedelta(days=1)

                    if arrival >= now and arrival - now < timedelta(hours=2):
                        future.append((row, arrival.strftime("%I:%M %p").lstrip("0")))
                except Exception as e:
                    log_debug(f"Time parsing failed: {e}")

            inbound, outbound = [], []
            for row, arrival_str in future:
                bus = {
                    "route_number": row["route_short_name"],
                    "destination": row.get("trip_headsign") or row.get("route_long_name", "N/A"),
                    "arrival_time": arrival_str,
                    "status": "Scheduled"
                }
                if row["direction_id"] == 1:
                    inbound.append(bus)
                else:
                    outbound.append(bus)

            inbound.sort(key=lambda x: datetime.strptime(x["arrival_time"], "%I:%M %p"))
            outbound.sort(key=lambda x: datetime.strptime(x["arrival_time"], "%I:%M %p"))

            return {
                "inbound": inbound[:3],
                "outbound": outbound[:3]
            }

        except Exception as e:
            log_debug(f"[SchedulerService Error] {e}")
            return {"inbound": [], "outbound": []}
