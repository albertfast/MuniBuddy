import os
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import math
import pandas as pd
from colorama import init, Fore, Style
import json
import asyncio
from .gtfs_service import load_gtfs_data

# Initialize colorama for colored output
init()

load_dotenv()
API_KEY = os.getenv("API_KEY")
AGENCY_IDS = os.getenv("AGENCY_ID", "SFMTA").split(',')


class BusService:
    def __init__(self):
        self.api_key = API_KEY
        self.base_url = "http://api.511.org/transit"
        self.agency_ids = AGENCY_IDS
        self.stops_cache = None
        self.gtfs_data = {}

        # Load GTFS data
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.muni_gtfs_path = os.path.normpath(os.path.join(base_dir, "../../gtfs_data/muni_gtfs-current"))
        self.bart_gtfs_path = os.path.normpath(os.path.join(base_dir, "../../gtfs_data/bart_gtfs-current"))

        print(f"[DEBUG] Muni GTFS path: {self.muni_gtfs_path}")
        print(f"[DEBUG] BART GTFS path: {self.bart_gtfs_path}")

        try:
            self.gtfs_data['routes'] = pd.read_csv(
                os.path.join(self.muni_gtfs_path, 'routes.txt'),
                dtype={'route_id': str}
            )
            self.gtfs_data['trips'] = pd.read_csv(
                os.path.join(self.muni_gtfs_path, 'trips.txt'),
                dtype={'trip_id': str, 'route_id': str, 'service_id': str}
            )
            self.gtfs_data['stops'] = pd.read_csv(
                os.path.join(self.muni_gtfs_path, 'stops.txt'),
                dtype={'stop_id': str}
            )
            self.gtfs_data['stop_times'] = pd.read_csv(
                os.path.join(self.muni_gtfs_path, 'stop_times.txt'),
                dtype={'stop_id': str, 'trip_id': str, 'arrival_time': str}
            )
            self.gtfs_data['calendar'] = pd.read_csv(
                os.path.join(self.muni_gtfs_path, 'calendar.txt'),
                dtype={
                    'service_id': str,
                    'monday': int,
                    'tuesday': int,
                    'wednesday': int,
                    'thursday': int,
                    'friday': int,
                    'saturday': int,
                    'sunday': int,
                    'start_date': int,
                    'end_date': int
                }
            )

            print(f"{Fore.GREEN}✓ GTFS data loaded successfully!{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}✗ Error loading GTFS data: {str(e)}{Style.RESET_ALL}")
            self.gtfs_data = {}  
                
    def _get_static_schedule(self, stop_id: str) -> Dict[str, Any]:
        """Get static schedule from GTFS data."""
        try:
            # Get current time
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            
            # Get active services for today
            weekday = now.strftime("%A").lower()
            active_services = self.gtfs_data['calendar'][
                (self.gtfs_data['calendar'][weekday] == 1) &
                (pd.to_numeric(self.gtfs_data['calendar']['start_date']) <= int(now.strftime("%Y%m%d"))) &
                (pd.to_numeric(self.gtfs_data['calendar']['end_date']) >= int(now.strftime("%Y%m%d")))
            ]['service_id']
            
            # Get trips for active services
            active_trips = self.gtfs_data['trips'][
                self.gtfs_data['trips']['service_id'].isin(active_services)
            ]
            
            # Get stop times for this stop
            stop_times = self.gtfs_data['stop_times'][
                self.gtfs_data['stop_times']['stop_id'] == stop_id
            ]
            
            # Merge with trips and routes
            schedule_data = stop_times.merge(
                active_trips[['trip_id', 'route_id', 'direction_id', 'trip_headsign']],
                on='trip_id'
            ).merge(
                self.gtfs_data['routes'][['route_id', 'route_short_name', 'route_long_name']],
                on='route_id'
            )
            
            # Normalize arrival times for comparison
            def normalize_time(time_str):
                try:
                    hours, minutes, seconds = map(int, time_str.split(':'))
                    if hours >= 24:  # Handle times past midnight
                        hours = hours % 24
                    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                except:
                    return time_str

            # Convert current_time to datetime for comparison
            current_dt = datetime.strptime(current_time, "%H:%M:%S")
            
            # Get next arrivals and normalize their times
            schedule_data['normalized_time'] = schedule_data['arrival_time'].apply(normalize_time)
            
            # Filter future arrivals within next 2 hours
            future_arrivals = []
            for _, row in schedule_data.iterrows():
                try:
                    arrival_time = datetime.strptime(row['normalized_time'], "%H:%M:%S")
                    time_diff = (arrival_time - current_dt).total_seconds() / 3600  # in hours
                    if 0 <= time_diff <= 2:  # Only show arrivals within next 2 hours
                        # Convert to local timezone
                        if arrival_time.hour < current_dt.hour:  # If arrival hour is less than current hour, it's next day
                            arrival_time = arrival_time + timedelta(days=1)
                        future_arrivals.append((row, arrival_time))
                except:
                    continue
            
            # Group by direction
            inbound = []
            outbound = []
            
            for row, arrival_time in future_arrivals:
                arrival_str = arrival_time.strftime("%I:%M %p")  # 12-hour format with AM/PM
                
                # Get destination and direction
                destination = row['trip_headsign'] if pd.notna(row['trip_headsign']) else row['route_long_name'].split(' - ')[-1]
                
                bus_info = {
                    'route_number': row['route_short_name'],
                    'destination': destination,
                    'arrival_time': arrival_str,
                    'status': 'Scheduled'
                }
                
                # Direction check based on destination and route name
                route_name = row['route_long_name'].lower()
                destination_lower = destination.lower()
                
                # Check for outbound indicators first
                if (any(term in destination_lower for term in ['ocean', 'beach', 'zoo', 'cliff']) or
                    any(term in route_name for term in ['outbound', 'ocean', 'beach', 'zoo']) or
                    row['direction_id'] == 0):
                    outbound.append(bus_info)
                # Then check for inbound indicators
                elif (any(term in destination_lower for term in ['downtown', 'market', 'ferry', 'transit center', 'terminal']) or
                    any(term in route_name for term in ['inbound', 'downtown', 'market', 'ferry']) or
                    row['direction_id'] == 1):
                    inbound.append(bus_info)
                # If still unclear, use direction_id as fallback
                else:
                    if row['direction_id'] == 0:
                        outbound.append(bus_info)
                    else:
                        inbound.append(bus_info)
            
            # Sort arrivals and limit
            inbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            outbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            
            return {
                'inbound': inbound[:2],  # Show only first 2 buses
                'outbound': outbound[:2]  # Show only first 2 buses
            }
            
        except Exception as e:
            print(f"{Fore.RED}✗ Error getting static schedule: {str(e)}{Style.RESET_ALL}")
            return {'inbound': [], 'outbound': []}

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.
        
        Args:
            lat1 (float): First point latitude
            lon1 (float): First point longitude
            lat2 (float): Second point latitude
            lon2 (float): Second point longitude
            
        Returns:
            float: Distance in miles
        """
        R = 3959  # Earth's radius in miles
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c

    async def _load_stops(self) -> List[Dict[str, Any]]:
        """
        Load all stops from GTFS data.
        
        Returns:
            List[Dict[str, Any]]: List of stops with their coordinates
        """
        if self.stops_cache is not None:
            return self.stops_cache
            
        try:
            # Read GTFS stops.txt file
            gtfs_path = os.path.join("gtfs_data/muni_gtfs-current", "stops.txt")
            
            if not os.path.exists(gtfs_path):
                print(f"GTFS stops file not found at: {gtfs_path}")
                return []
                
            # Read GTFS stops.txt file
            stops = []
            with open(gtfs_path, 'r') as f:
                # Skip first line (headers)
                headers = f.readline().strip().split(',')
                
                for line in f:
                    values = line.strip().split(',')
                    stop = dict(zip(headers, values))
                    stops.append({
                        'stop_id': stop['stop_id'],
                        'stop_name': stop['stop_name'],
                        'stop_lat': float(stop['stop_lat']),
                        'stop_lon': float(stop['stop_lon'])
                    })
            
            self.stops_cache = stops
            return stops
            
        except Exception as e:
            print(f"Error loading stops: {str(e)}")
            return []

    async def find_nearby_stops(self, lat: float, lon: float, radius_miles: float = 0.1, limit: int = 3) -> List[Dict[str, Any]]:
        stops = await self._load_stops()
        nearby_stops = []

        for stop in stops:
            distance = self._calculate_distance(lat, lon, stop['stop_lat'], stop['stop_lon'])
            if distance <= radius_miles:
                # Get route information from GTFS data
                stop_times = self.gtfs_data['stop_times'][
                    self.gtfs_data['stop_times']['stop_id'] == stop['stop_id']
                ]

                trips = self.gtfs_data['trips'][
                    self.gtfs_data['trips']['trip_id'].isin(stop_times['trip_id'])
                ]

                routes = self.gtfs_data['routes'][
                    self.gtfs_data['routes']['route_id'].isin(trips['route_id'])
                ].drop_duplicates()

                # Prepare route information for the stop
                route_info = []
                for _, route in routes.iterrows():
                    # Get the final destination (last part of route name)
                    destination = route['route_long_name'].split(' - ')[-1] if ' - ' in route['route_long_name'] else route['route_long_name']

                    route_info.append({
                        'route_id': route['route_id'],
                        'route_number': route['route_short_name'],
                        'destination': destination
                    })

                stop_info = stop.copy()
                stop_info['stop_id'] = str(stop['stop_id'])
                stop_info['distance_miles'] = round(distance, 2)
                stop_info['routes'] = route_info
                nearby_stops.append(stop_info)

        # Sort by distance
        nearby_stops.sort(key=lambda x: x['distance_miles'])
        return nearby_stops[:limit]


    async def get_nearby_buses(self, lat: float, lon: float, radius_miles: float = 0.1) -> Dict[str, Any]:
        nearby_stops = await self.find_nearby_stops(lat, lon, radius_miles)

        tasks = [
            self.get_stop_schedule(stop['stop_id'])
            for stop in nearby_stops
        ]

        schedules = await asyncio.gather(*tasks, return_exceptions=True)

        result = {}
        for stop, schedule in zip(nearby_stops, schedules):
            # Eğer görev hata döndürdüyse, logla ve atla
            if isinstance(schedule, Exception):
                print(f"✗ Error for stop {stop['stop_id']}: {schedule}")
                continue

            result[stop['stop_id']] = {
                'stop_id': stop['stop_id'],
                'stop_name': stop['stop_name'],
                'distance_miles': stop['distance_miles'],
                'routes': stop.get('routes', []),
                'schedule': schedule
            }

        return result

    async def fetch_stop_data(self, stop_id: str) -> Optional[Dict[str, Any]]:
        """First get static data from GTFS, then combine with real-time data."""
        try:
            # First get static schedule from GTFS
            static_schedule = self._get_static_schedule(stop_id)
            
            # Now try to get real-time data
            url = f"{self.base_url}/StopMonitoring"
            params = {
                "api_key": self.api_key,
                "agency": "SF",
                "stopId": stop_id,
                "format": "json"
            }
            
            try:
                response = requests.get(url, params=params)
                if response.status_code != 200:
                    return {
                        'inbound': static_schedule['inbound'][:2],
                        'outbound': static_schedule['outbound'][:2]
                    }
                
                content = response.content.decode('utf-8-sig')
                data = json.loads(content)
                
                delivery = data.get("ServiceDelivery", {})
                monitoring = delivery.get("StopMonitoringDelivery", {})
                stops = monitoring.get("MonitoredStopVisit", [])
                
                if not stops:
                    return {
                        'inbound': static_schedule['inbound'][:2],
                        'outbound': static_schedule['outbound'][:2]
                    }
                
                # Process real-time data
                inbound = []
                outbound = []
                now = datetime.now().replace(tzinfo=None)  # Remove timezone
                
                for stop in stops:
                    journey = stop.get("MonitoredVehicleJourney", {})
                    line_ref = journey.get("LineRef", "").replace("SF:", "")
                    direction = journey.get("DirectionRef", "").lower()
                    destination_name = journey.get("DestinationName", [""])[0]
                    
                    # Get route information from GTFS
                    try:
                        route_info = self.gtfs_data['routes'][
                            self.gtfs_data['routes']['route_id'] == line_ref
                        ].iloc[0]
                        
                        line_name = route_info['route_long_name']
                        route_number = route_info['route_short_name']
                    except:
                        line_name = destination_name
                        route_number = line_ref
                    
                    # Get arrival times
                    call = journey.get("MonitoredCall", {})
                    expected = call.get("ExpectedArrivalTime")
                    aimed = call.get("AimedArrivalTime")
                    
                    if not expected and not aimed:
                        continue
                        
                    arrival_time = None
                    if expected:
                        arrival_time = datetime.fromisoformat(expected.replace('Z', '+00:00')).replace(tzinfo=None)
                    elif aimed:
                        arrival_time = datetime.fromisoformat(aimed.replace('Z', '+00:00')).replace(tzinfo=None)
                    
                    if not arrival_time:
                        continue

                    # Only show arrivals within next 2 hours
                    time_diff = (arrival_time - now).total_seconds() / 3600  # in hours
                    if time_diff < 0 or time_diff > 2:
                        continue
                        
                    # Calculate delay
                    delay_minutes = 0
                    if expected and aimed:
                        expected_dt = datetime.fromisoformat(expected.replace('Z', '+00:00')).replace(tzinfo=None)
                        aimed_dt = datetime.fromisoformat(aimed.replace('Z', '+00:00')).replace(tzinfo=None)
                        delay_minutes = int((expected_dt - aimed_dt).total_seconds() / 60)
                    
                    # Determine status
                    status = "On Time"
                    if delay_minutes > 0:
                        status = f"Delayed ({delay_minutes} min)"
                    elif delay_minutes < 0:
                        status = f"Early ({abs(delay_minutes)} min)"
                    
                    # Prepare bus information
                    bus_info = {
                        'route_number': route_number,
                        'destination': destination_name,
                        'arrival_time': arrival_time.strftime("%I:%M %p"),
                        'status': status
                    }
                    
                    # Direction check based on destination and route name
                    route_name = line_name.lower()
                    destination_lower = destination_name.lower()
                    
                    # Check for outbound indicators first
                    if (any(term in destination_lower for term in ['ocean', 'beach', 'zoo', 'cliff']) or
                        any(term in route_name for term in ['outbound', 'ocean', 'beach', 'zoo']) or
                        direction == "0"):
                        outbound.append(bus_info)
                    # Then check for inbound indicators
                    elif (any(term in destination_lower for term in ['downtown', 'market', 'ferry', 'transit center', 'terminal']) or
                        any(term in route_name for term in ['inbound', 'downtown', 'market', 'ferry']) or
                        direction == "1"):
                        inbound.append(bus_info)
                    # If still unclear, use direction as fallback
                    else:
                        if direction == "0":
                            outbound.append(bus_info)
                        else:
                            inbound.append(bus_info)
                
                # Sort arrivals and limit
                inbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
                outbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
                
                return {
                    'inbound': inbound[:2],  # Show only first 2 buses
                    'outbound': outbound[:2]  # Show only first 2 buses
                }
                
            except Exception as e:
                print(f"{Fore.RED}✗ Error fetching real-time data: {str(e)}{Style.RESET_ALL}")
                return {
                    'inbound': static_schedule['inbound'][:2],
                    'outbound': static_schedule['outbound'][:2]
                }
                
        except Exception as e:
            print(f"{Fore.RED}✗ Unexpected error: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}⚠️ Error details: {type(e).__name__}{Style.RESET_ALL}")
            return {'inbound': [], 'outbound': []}

    async def get_stop_schedule(self, stop_id: str) -> Optional[Dict[str, Any]]:
        """
        Get schedule for a specific stop, trying real-time data first, falling back to GTFS.
        
        Args:
            stop_id (str): The ID of the stop to get schedule for
            
        Returns:
            Optional[Dict[str, Any]]: Stop schedule or None if error
        """
        # Try real-time data first
        real_time_data = await self.fetch_stop_data(stop_id)
        if real_time_data and (real_time_data['inbound'] or real_time_data['outbound']):
            return real_time_data
            
        # Fall back to static GTFS data
        return self._get_static_schedule(stop_id)

    async def get_next_buses(self, stop_id: str, direction: str = "both", limit: int = 5) -> Optional[Dict[str, Any]]:
        """
        Get next buses for a specific stop and direction.
        
        Args:
            stop_id (str): The ID of the stop to monitor
            direction (str): Direction to check ("inbound", "outbound", or "both")
            limit (int): Maximum number of buses to return per direction
            
        Returns:
            Optional[Dict[str, Any]]: Next buses or None if error
        """
        data = await self.fetch_stop_data(stop_id)
        if not data:
            return None
            
        result = {}
        
        if direction in ["both", "inbound"]:
            result["inbound"] = data["inbound"][:limit]
        if direction in ["both", "outbound"]:
            result["outbound"] = data["outbound"][:limit]
            
        return result