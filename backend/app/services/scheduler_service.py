from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import requests
import json
import pandas as pd
import os

from app.config import settings
from app.services.gtfs_service import load_gtfs_data
from app.utils.json_cleaner import clean_api_response
from app.utils.xml_parser import xml_to_json

class SchedulerService:
    def __init__(self):
        self.api_key = settings.API_KEY
        self.base_url = settings.TRANSIT_511_BASE_URL
        self.agency = settings.DEFAULT_AGENCY

        # Load GTFS data using provided path from settings
        (
            self.routes_df,
            self.trips_df,
            self.stops_df,
            self.stop_times_df,
            self.calendar_df
        ) = load_gtfs_data(settings.MUNI_GTFS_PATH)

    def _normalize_time(self, time_str: str) -> str:
        try:
            hours, minutes, seconds = map(int, time_str.split(':'))
            if hours >= 24:
                hours = hours % 24
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception as e:
            print(f"Error normalizing time {time_str}: {str(e)}")
            return "00:00:00"

    def calculate_optimal_bus(self, arrival_time: str, schedule_data: list) -> Optional[Dict[str, Any]]:
        try:
            target_time = datetime.fromisoformat(arrival_time.replace('Z', '+00:00'))
            best_bus = None
            min_time_diff = float('inf')

            for schedule in schedule_data:
                schedule_time = datetime.fromisoformat(schedule.arrival_time.replace('Z', '+00:00'))
                time_diff = (target_time - schedule_time).total_seconds()
                if 0 <= time_diff < min_time_diff:
                    min_time_diff = time_diff
                    best_bus = schedule
            return best_bus
        except Exception as e:
            print(f"Error calculating optimal bus: {str(e)}")
            return None

    async def get_schedule_for_stop(self, stop_id: str, line_id: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        try:
            schedule_data = self._get_schedule_from_gtfs(stop_id, line_id)
            schedule_info = self._prepare_schedule_info(schedule_data)
            return schedule_info
        except Exception as e:
            print(f"Error getting schedule: {str(e)}")
            return None

    async def _get_schedule_from_511(self, stop_id: str, line_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            api_url = f"{self.base_url}/StopMonitoring"
            params = {
                "api_key": self.api_key,
                "agency": self.agency,
                "stop_id": stop_id,
                "format": "json",
                "minutes_before": 30,
                "minutes_after": 30
            }
            if line_id:
                params["line_id"] = line_id

            response = requests.get(api_url, params=params)
            response.raise_for_status()

            data = response.json()
            cleaned_data = clean_api_response(json.dumps(data))

            stops = cleaned_data.get("ServiceDelivery", {}).get("StopMonitoringDelivery", {}).get("MonitoredStopVisit", [])
            if not stops:
                return None

            schedule = []
            for stop in stops:
                bus_info = stop.get("MonitoredVehicleJourney", {})
                schedule.append({
                    "line_id": bus_info.get("LineRef"),
                    "line_name": bus_info.get("LineName"),
                    "direction": bus_info.get("DirectionRef"),
                    "expected_arrival": bus_info.get("MonitoredCall", {}).get("ExpectedArrivalTime"),
                    "scheduled_arrival": bus_info.get("MonitoredCall", {}).get("ScheduledArrivalTime"),
                    "status": bus_info.get("MonitoredCall", {}).get("ArrivalStatus"),
                    "delay_minutes": bus_info.get("MonitoredCall", {}).get("Delay", 0)
                })
            return schedule
        except Exception as e:
            print(f"Error getting schedule from 511.org: {str(e)}")
            return None

    async def get_best_bus_for_arrival(self, destination: str, arrival_time: str, stop_id: str) -> Optional[Dict[str, Any]]:
        try:
            stop_schedule = self.stop_times_df[self.stop_times_df['stop_id'] == stop_id]
            if stop_schedule.empty:
                return None

            today = datetime.now().strftime('%Y%m%d')
            active_services = self.calendar_df[
                (self.calendar_df['start_date'] <= int(today)) &
                (self.calendar_df['end_date'] >= int(today))
            ]
            if active_services.empty:
                return None

            target_time = datetime.strptime(arrival_time, "%Y-%m-%dT%H:%M:%SZ")
            best_trip = None
            min_time_diff = float('inf')

            for _, row in stop_schedule.iterrows():
                trip_time = datetime.strptime(row['arrival_time'], "%H:%M:%S")
                time_diff = abs((trip_time - target_time).total_seconds())
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    best_trip = row

            if best_trip is not None:
                trip_info = self.trips_df[self.trips_df['trip_id'] == best_trip['trip_id']].iloc[0]
                route_info = self.routes_df[self.routes_df['route_id'] == trip_info['route_id']].iloc[0]

                return {
                    'line_id': route_info['route_short_name'],
                    'line_name': route_info['route_long_name'],
                    'scheduled_arrival': best_trip['arrival_time'],
                    'status': 'scheduled'
                }
            return None
        except Exception as e:
            print(f"Error getting best bus: {str(e)}")
            return None

    async def get_schedule(self, stop_id: str) -> Dict[str, Any]:
        try:
            static_schedule = await self.get_schedule_for_stop(stop_id) or []
            realtime_schedule = await self._get_schedule_from_511(stop_id) or []

            schedule_data = []
            for bus in realtime_schedule:
                schedule_data.append({
                    'line_id': bus['line_id'],
                    'line_name': bus['line_name'],
                    'scheduled_arrival': bus['scheduled_arrival'],
                    'status': bus['status'] if bus['status'] else 'Scheduled'
                })

            realtime_routes = set(bus['line_id'] for bus in realtime_schedule)
            for bus in static_schedule:
                if bus['line_id'] not in realtime_routes:
                    schedule_data.append(bus)

            if not schedule_data:
                return {'inbound': [], 'outbound': []}

            inbound, outbound = [], []
            for bus in schedule_data:
                line_name = bus['line_name'].lower()
                destination = bus['line_name'].split(' - ')[-1]
                normalized_time = self._normalize_time(bus['scheduled_arrival'])
                bus_info = {
                    'route_number': bus['line_id'],
                    'destination': destination,
                    'arrival_time': datetime.strptime(normalized_time, "%H:%M:%S").strftime("%I:%M %p"),
                    'status': bus['status'].title()
                }
                if any(term in line_name for term in ['ocean', 'beach', 'zoo', 'cliff', 'outbound']) or \
                   any(term in destination.lower() for term in ['ocean', 'beach', 'zoo', 'cliff']):
                    outbound.append(bus_info)
                elif any(term in line_name for term in ['downtown', 'market', 'ferry', 'inbound']) or \
                     any(term in destination.lower() for term in ['downtown', 'market', 'ferry', 'transit center', 'terminal']):
                    inbound.append(bus_info)
                else:
                    outbound.append(bus_info)

            inbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            outbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))

            return {
                'inbound': inbound[:2],
                'outbound': outbound[:2]
            }
        except Exception as e:
            print(f"Error getting schedule: {str(e)}")
            return {'inbound': [], 'outbound': []}
