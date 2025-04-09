import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import requests
from app.config import settings
from app.utils.json_cleaner import clean_api_response

class SchedulerService:
    def __init__(self, agency_id: str = settings.DEFAULT_AGENCY.lower()):
        self.api_key = settings.API_KEY
        self.base_url = settings.TRANSIT_511_BASE_URL

        agency_map = {
            "SFMTA": "muni",
            "MUNI": "muni",
            "SF": "muni",
            "BART": "bart"
        }
        normalized_agency = agency_map.get(agency_id.upper(), agency_id.lower())
        self.agency = normalized_agency.upper()

        gtfs_data = settings.get_gtfs_data(normalized_agency)
        if not gtfs_data:
            raise ValueError(f"GTFS data for agency '{normalized_agency}' not loaded")

        (
            self.routes_df,
            self.trips_df,
            self.stops_df,
            self.stop_times_df,
            self.calendar_df
        ) = gtfs_data

    def _normalize_time(self, time_str: str) -> str:
        try:
            hours, minutes, seconds = map(int, time_str.split(':'))
            if hours >= 24:
                hours = hours % 24
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception as e:
            print(f"Error normalizing time {time_str}: {str(e)}")
            return "00:00:00"

    async def get_schedule(self, stop_id: str) -> Dict[str, Any]:
        try:
            print(f"[INFO] Getting schedule for stop {stop_id}")
            static_schedule = await self.get_schedule_for_stop(stop_id) or []
            print(f"[INFO] Static schedule for stop {stop_id}: {len(static_schedule)} entries")

            realtime_schedule = await self._get_schedule_from_511(stop_id) or []
            print(f"[INFO] Realtime schedule for stop {stop_id}: {len(realtime_schedule)} entries")

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
            print(f"[ERROR] Error getting schedule for stop {stop_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'inbound': [], 'outbound': []}

    async def get_schedule_for_stop(self, stop_id: str, line_id: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        try:
            schedule_data = self._get_schedule_from_gtfs(stop_id, line_id)
            return self._prepare_schedule_info(schedule_data)
        except Exception as e:
            print(f"Error getting GTFS schedule: {str(e)}")
            return None

    async def fetch_real_time_stop_data(self, stop_id: str, line_id: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        try:
            return await self._get_schedule_from_511(stop_id, line_id)
        except Exception as e:
            print(f"Error in fetch_real_time_stop_data: {str(e)}")
            return None

    async def _get_schedule_from_511(self, stop_id: str, line_id: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        try:
            print(f"[DEBUG] Requesting 511 API data for stop {stop_id}")
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
                return []

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
            return []

    def _get_schedule_from_gtfs(self, stop_id: str, line_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            current_day = now.strftime("%A").lower()
            current_date = int(now.strftime("%Y%m%d"))

            active_services = self.calendar_df[
                (self.calendar_df['start_date'] <= current_date) &
                (self.calendar_df['end_date'] >= current_date) &
                (self.calendar_df[current_day] == '1')
            ]['service_id'].tolist()

            if not active_services:
                return []

            active_trips = self.trips_df[self.trips_df['service_id'].isin(active_services)]
            stop_times = self.stop_times_df[self.stop_times_df['stop_id'] == stop_id]
            if stop_times.empty:
                return []

            valid_stop_times = stop_times[
                stop_times['trip_id'].isin(active_trips['trip_id']) &
                (stop_times['arrival_time'] > current_time)
            ]

            if valid_stop_times.empty:
                valid_stop_times = stop_times[
                    stop_times['trip_id'].isin(active_trips['trip_id']) &
                    (stop_times['arrival_time'].str.startswith(('24:', '25:', '26:', '27:')))
                ]
                if valid_stop_times.empty:
                    return []

            if line_id:
                route_ids = self.routes_df[self.routes_df['route_short_name'] == line_id]['route_id'].tolist()
                if not route_ids:
                    return []
                line_trips = active_trips[active_trips['route_id'].isin(route_ids)]['trip_id'].tolist()
                valid_stop_times = valid_stop_times[valid_stop_times['trip_id'].isin(line_trips)]
                if valid_stop_times.empty:
                    return []

            valid_stop_times = valid_stop_times.sort_values('arrival_time').head(10)
            schedule_data = []

            for _, row in valid_stop_times.iterrows():
                trip_id = row['trip_id']
                trip_info = active_trips[active_trips['trip_id'] == trip_id].iloc[0]
                route_id = trip_info['route_id']
                route_info = self.routes_df[self.routes_df['route_id'] == route_id].iloc[0]

                schedule_data.append({
                    'line_id': route_info['route_short_name'],
                    'line_name': route_info['route_long_name'],
                    'scheduled_arrival': row['arrival_time'],
                    'status': 'Scheduled'
                })

            return schedule_data
        except Exception as e:
            print(f"[ERROR] Error in _get_schedule_from_gtfs: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def _prepare_schedule_info(self, schedule_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return schedule_data if schedule_data else []
