from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from app.utils.json_cleaner import clean_api_response
from app.utils.xml_parser import xml_to_json
import requests
import json
import pandas as pd
from app.config import settings
import os
from app.services.gtfs_service import load_gtfs_data

class SchedulerService:
    def __init__(self):
        # Load config from settings
        self.api_key = settings.API_KEY
        self.base_url = settings.TRANSIT_511_BASE_URL
        self.agency = settings.DEFAULT_AGENCY
        
        # Load GTFS data
        self.routes_df, self.trips_df, self.stops_df, self.stop_times_df, self.calendar_df = load_gtfs_data()
        
        print(f"Loaded {len(self.stops_df)} stops")
        print(f"Loaded {len(self.stop_times_df)} stop times")
        print(f"Loaded {len(self.trips_df)} trips")
        print(f"Loaded {len(self.routes_df)} routes")
        print(f"Loaded {len(self.calendar_df)} calendar entries")

    def _normalize_time(self, time_str: str) -> str:
        """Convert times greater than 24 hours to standard format."""
        try:
            hours, minutes, seconds = map(int, time_str.split(':'))
            if hours >= 24:
                hours = hours % 24
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception as e:
            print(f"Error normalizing time {time_str}: {str(e)}")
            return "00:00:00"

    def calculate_optimal_bus(self, arrival_time: str, schedule_data: list) -> Optional[Dict[str, Any]]:
        """
        Finds the best bus option for a given arrival time.
        
        Args:
            arrival_time (str): Target arrival time in ISO format
            schedule_data (list): List of bus schedules
            
        Returns:
            Optional[Dict[str, Any]]: Best matching bus schedule or None
        """
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

    async def get_schedule_for_stop(
        self,
        stop_id: str,
        line_id: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Get schedule for a specific stop"""
        try:
            # Get schedule from GTFS data
            schedule_data = self._get_schedule_from_gtfs(stop_id, line_id)
            
            # Prepare schedule information
            schedule_info = self._prepare_schedule_info(schedule_data)
            
            return schedule_info
            
        except Exception as e:
            print(f"Error getting schedule: {str(e)}")
            return None

    async def _get_schedule_from_511(
        self,
        stop_id: str,
        line_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """511.org API'sinden program bilgilerini al"""
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
        """Get the best bus for a specific arrival time"""
        try:
            # GTFS verilerinden en uygun seferi bul
            stop_schedule = self.stop_times_df[self.stop_times_df['stop_id'] == stop_id]
            if stop_schedule.empty:
                return None
            
            # Aktif servisleri kontrol et
            today = datetime.now().strftime('%Y%m%d')
            active_services = self.calendar_df[
                (self.calendar_df['start_date'] <= int(today)) & 
                (self.calendar_df['end_date'] >= int(today))
            ]
            
            if active_services.empty:
                return None
            
            # En uygun seferi bul
            target_time = datetime.strptime(arrival_time, "%Y-%m-%dT%H:%M:%SZ")
            best_trip = None
            min_time_diff = float('inf')
            
            for _, row in stop_schedule.iterrows():
                trip_time = datetime.strptime(row['arrival_time'], "%H:%M:%S")
                time_diff = abs((trip_time - target_time).total_seconds())
                
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    best_trip = row
            
            if best_trip:
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
        """Get schedule for a specific stop."""
        try:
            # Get static schedule from GTFS data
            static_schedule = await self.get_schedule_for_stop(stop_id)
            if not static_schedule:
                static_schedule = []
            
            # Get real-time schedule from 511 API
            realtime_schedule = await self._get_schedule_from_511(stop_id)
            if not realtime_schedule:
                realtime_schedule = []
            
            # Combine static and real-time schedules
            schedule_data = []
            
            # Add real-time data first (it's more accurate)
            for bus in realtime_schedule:
                schedule_data.append({
                    'line_id': bus['line_id'],
                    'line_name': bus['line_name'],
                    'scheduled_arrival': bus['scheduled_arrival'],
                    'status': bus['status'] if bus['status'] else 'Scheduled'
                })
            
            # Add static data for routes not in real-time data
            realtime_routes = set(bus['line_id'] for bus in realtime_schedule)
            for bus in static_schedule:
                if bus['line_id'] not in realtime_routes:
                    schedule_data.append(bus)
            
            if not schedule_data:
                return {'inbound': [], 'outbound': []}
            
            # Group by direction
            inbound = []
            outbound = []
            
            for bus in schedule_data:
                # Get destination from line name
                line_name = bus['line_name'].lower()
                destination = bus['line_name'].split(' - ')[-1]
                
                # Normalize arrival time
                normalized_time = self._normalize_time(bus['scheduled_arrival'])
                
                bus_info = {
                    'route_number': bus['line_id'],
                    'destination': destination,
                    'arrival_time': datetime.strptime(normalized_time, "%H:%M:%S").strftime("%I:%M %p"),
                    'status': bus['status'].title()
                }
                
                # Direction check based on destination and line name
                if (any(term in line_name for term in ['ocean', 'beach', 'zoo', 'cliff', 'outbound']) or
                    any(term in destination.lower() for term in ['ocean', 'beach', 'zoo', 'cliff'])):
                    outbound.append(bus_info)
                elif (any(term in line_name for term in ['downtown', 'market', 'ferry', 'inbound']) or
                    any(term in destination.lower() for term in ['downtown', 'market', 'ferry', 'transit center', 'terminal'])):
                    inbound.append(bus_info)
                else:
                    # If direction is unclear, put in outbound by default
                    outbound.append(bus_info)
            
            # Sort by arrival time
            inbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            outbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            
            return {
                'inbound': inbound[:2],  # Show only first 2 buses
                'outbound': outbound[:2]  # Show only first 2 buses
            }
            
        except Exception as e:
            print(f"Error getting schedule: {str(e)}")
            return {'inbound': [], 'outbound': []}