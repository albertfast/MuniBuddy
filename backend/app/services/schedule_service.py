from typing import Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from colorama import Fore, Style
from app.services.gtfs_service import GTFSService
from app.services.debug_logger import log_debug

class SchedulerService:
    def get_schedule(self, stop_id: str, agency: str = "muni") -> Dict[str, Any]:
        agency = agency.lower()
        log_debug(f"[SchedulerService] Looking up static schedule for stop: {stop_id}, agency: {agency}")

        gtfs = GTFSService(agency)

        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            weekday = now.strftime("%A").lower()

            stop_times_df = gtfs._query("stop_times", f"stop_id = '{stop_id}'")
            trips_df = gtfs._query("trips")
            calendar_df = gtfs._query("calendar")
            routes_df = gtfs._query("routes")

            if stop_times_df.empty or trips_df.empty or calendar_df.empty or routes_df.empty:
                log_debug("One or more GTFS components are missing or empty.")
                return {"inbound": [], "outbound": []}

            service_ids = calendar_df[
                (calendar_df[weekday] == 1) &
                (pd.to_numeric(calendar_df["start_date"]) <= int(now.strftime("%Y%m%d"))) &
                (pd.to_numeric(calendar_df["end_date"]) >= int(now.strftime("%Y%m%d")))
            ]["service_id"].tolist()

            active_trips = trips_df[trips_df["service_id"].isin(service_ids)]

            schedule_data = stop_times_df.merge(
                active_trips[["trip_id", "route_id", "direction_id", "trip_headsign"]], on="trip_id"
            ).merge(
                routes_df[["route_id", "route_short_name", "route_long_name"]], on="route_id"
            )

            current_dt = datetime.strptime(current_time, "%H:%M:%S")

            future_arrivals = []
            for _, row in schedule_data.iterrows():
                try:
                    hours, minutes, seconds = map(int, row["arrival_time"].split(":"))
                    extra_days = hours // 24
                    normalized_hours = hours % 24

                    arrival_str = f"{normalized_hours:02d}:{minutes:02d}:{seconds:02d}"
                    arrival_time = datetime.strptime(arrival_str, "%H:%M:%S")

                    if extra_days > 0:
                        arrival_time += timedelta(days=extra_days)
                    if normalized_hours < current_dt.hour and extra_days == 0:
                        arrival_time += timedelta(days=1)

                    time_diff = (arrival_time - current_dt).total_seconds() / 3600
                    if 0 <= time_diff <= 2:
                        formatted_time = arrival_time.strftime("%I:%M %p").lstrip("0")
                        future_arrivals.append((row, formatted_time))
                except ValueError as e:
                    log_debug(f"Error parsing time {row['arrival_time']}: {e}")
                    continue

            inbound = []
            outbound = []

            for row, arrival_str in future_arrivals:
                destination = row["trip_headsign"] if pd.notna(row["trip_headsign"]) else row["route_long_name"]
                bus_info = {
                    "route_number": row["route_short_name"],
                    "destination": destination,
                    "arrival_time": arrival_str,
                    "status": "Scheduled"
                }
                if row["direction_id"] == 1:
                    inbound.append(bus_info)
                else:
                    outbound.append(bus_info)

            inbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            outbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))

            return {"inbound": inbound[:2], "outbound": outbound[:2]}

        except Exception as e:
            log_debug(f"Static schedule error for stop {stop_id}, agency {agency}: {e}")
            return {"inbound": [], "outbound": []}