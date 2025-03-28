import os
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import math
import pandas as pd
from colorama import init, Fore, Style
import json
from .gtfs_service import load_gtfs_data
import pytz

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

        # GTFS paths (relative to backend folder)
        self.bart_gtfs_path = "gtfs_data/bart_gtfs-current"
        self.muni_gtfs_path = "gtfs_data/muni_gtfs-current"

        # Load GTFS data
        try:
            routes_df, trips_df, stops_df, stop_times_df, calendar_df = load_gtfs_data()
            self.gtfs_data['routes'] = routes_df
            self.gtfs_data['trips'] = trips_df
            self.gtfs_data['stops'] = stops_df
            self.gtfs_data['stop_times'] = stop_times_df
            self.gtfs_data['calendar'] = calendar_df
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
            
            if stop_times.empty:
                print(f"{Fore.YELLOW}⚠️ No stop times found for stop {stop_id}{Style.RESET_ALL}")
                return {'inbound': [], 'outbound': []}
            
            # Merge with trips and routes
            schedule_data = stop_times.merge(
                active_trips[['trip_id', 'route_id', 'direction_id', 'trip_headsign']],
                on='trip_id'
            ).merge(
                self.gtfs_data['routes'][['route_id', 'route_short_name', 'route_long_name']],
                on='route_id'
            )
            
            if schedule_data.empty:
                print(f"{Fore.YELLOW}⚠️ No schedule data found for stop {stop_id}{Style.RESET_ALL}")
                return {'inbound': [], 'outbound': []}
            
            # Convert current_time to datetime for comparison
            current_dt = datetime.strptime(current_time, "%H:%M:%S")
            
            # Filter future arrivals within next 2 hours
            future_arrivals = []
            for _, row in schedule_data.iterrows():
                try:
                    # Parse arrival time handling times past midnight
                    hours, minutes, seconds = map(int, row['arrival_time'].split(':'))
                    extra_days = hours // 24
                    normalized_hours = hours % 24
                    
                    arrival_str = f"{normalized_hours:02d}:{minutes:02d}:{seconds:02d}"
                    arrival_time = datetime.strptime(arrival_str, "%H:%M:%S")
                    
                    # Add extra days if the time was >24 hours
                    if extra_days > 0:
                        arrival_time = arrival_time + timedelta(days=extra_days)
                    
                    # Handle times past midnight for current day
                    if normalized_hours < current_dt.hour and extra_days == 0:
                        arrival_time = arrival_time + timedelta(days=1)
                    
                    time_diff = (arrival_time - current_dt).total_seconds() / 3600
                    if 0 <= time_diff <= 2:
                        arrival_str = arrival_time.strftime("%I:%M %p").lstrip('0')
                        future_arrivals.append((row, arrival_str))
                except ValueError as e:
                    print(f"{Fore.YELLOW}⚠️ Error parsing time {row['arrival_time']}: {e}{Style.RESET_ALL}")
                    continue
            
            # Group by direction
            inbound = []
            outbound = []
            
            for row, arrival_str in future_arrivals:
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
                
                if (any(term in destination_lower for term in ['ocean', 'beach', 'zoo', 'cliff']) or
                    any(term in route_name for term in ['outbound', 'ocean', 'beach', 'zoo']) or
                    row['direction_id'] == 0):
                    outbound.append(bus_info)
                elif (any(term in destination_lower for term in ['downtown', 'market', 'ferry', 'transit center', 'terminal']) or
                    any(term in route_name for term in ['inbound', 'downtown', 'market', 'ferry']) or
                    row['direction_id'] == 1):
                    inbound.append(bus_info)
                else:
                    if row['direction_id'] == 0:
                        outbound.append(bus_info)
                    else:
                        inbound.append(bus_info)
            
            # Sort arrivals and limit
            inbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            outbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            
            return {
                'inbound': inbound[:2],
                'outbound': outbound[:2]
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
            # Use stops from GTFS data instead of reading from file
            if 'stops' not in self.gtfs_data or self.gtfs_data['stops'].empty:
                print(f"{Fore.RED}✗ No stops data in GTFS{Style.RESET_ALL}")
                return []

            stops = []
            for _, row in self.gtfs_data['stops'].iterrows():
                stops.append({
                    'stop_id': row['stop_id'],
                    'stop_name': row['stop_name'],
                    'stop_lat': float(row['stop_lat']),
                    'stop_lon': float(row['stop_lon'])
                })

            self.stops_cache = stops
            print(f"{Fore.GREEN}✓ Loaded {len(stops)} stops from GTFS data{Style.RESET_ALL}")
            return stops

        except Exception as e:
            print(f"{Fore.RED}✗ Error loading stops: {str(e)}{Style.RESET_ALL}")
            return []

    async def find_nearby_stops(self, lat: float, lon: float, radius_miles: float = 0.1, limit: int = 3) -> List[Dict[str, Any]]:
        stops = await self._load_stops()
        nearby_stops = []

        for stop in stops:
            distance = self._calculate_distance(lat, lon, stop['stop_lat'], stop['stop_lon'])
            if distance <= radius_miles:
                # Get route information from GTFS data
                original_stop_id = stop['stop_id']
                api_stop_id = original_stop_id[1:] if original_stop_id.startswith('1') else original_stop_id

                try:
                    stop_times = self.gtfs_data['stop_times'][
                        self.gtfs_data['stop_times']['stop_id'] == original_stop_id
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
                    stop_info['distance_miles'] = round(distance, 2)
                    stop_info['routes'] = route_info
                    stop_info['id'] = api_stop_id  # Frontend için
                    stop_info['stop_id'] = api_stop_id  # API çağrıları için
                    stop_info['gtfs_stop_id'] = original_stop_id  # GTFS sorguları için
                    nearby_stops.append(stop_info)

                except KeyError as e:
                    print(f"{Fore.RED}✗ KeyError while processing stop {original_stop_id}: {e}{Style.RESET_ALL}")
                    continue
                except Exception as e:
                    print(f"{Fore.RED}✗ Error while processing stop {original_stop_id}: {e}{Style.RESET_ALL}")
                    continue

        # Sort by distance
        nearby_stops.sort(key=lambda x: x['distance_miles'])
        return nearby_stops[:limit]

    async def get_nearby_buses(self, lat: float = None, lon: float = None, stop_id: str = None, radius_miles: float = 0.1) -> Dict[str, Any]:
        """Get nearby buses by lat/lon or stop_id."""
        result = {}

        if lat is not None and lon is not None:
            # Find nearby stops based on coordinates
            nearby_stops = await self.find_nearby_stops(lat, lon, radius_miles)

            for stop in nearby_stops:
                try:
                    schedule = await self.get_stop_schedule(stop['stop_id'])
                    if schedule:
                        result[stop['id']] = {
                            'stop_name': stop['stop_name'],
                            'id': stop['id'],
                            'distance_miles': stop['distance_miles'],
                            'routes': stop.get('routes', []),
                            'schedule': schedule,
                            'gtfs_stop_id': stop['gtfs_stop_id']
                        }
                except Exception as e:
                    print(f"{Fore.RED}✗ Error processing stop {stop.get('stop_id', 'Unknown')}: {e}{Style.RESET_ALL}")

        elif stop_id:
            # Get schedule directly for a given stop_id
            try:
                schedule = await self.get_stop_schedule(stop_id)
                if schedule:
                    # Create a "fake" stop result
                    result[stop_id] = {
                        'stop_name': 'Unknown Stop',
                        'id': stop_id,
                        'distance_miles': 0,
                        'routes': [],
                        'schedule': schedule,
                        'gtfs_stop_id': stop_id
                    }
            except Exception as e:
                print(f"{Fore.RED}✗ Error processing stop {stop_id}: {e}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠️ No lat/lon or stop_id provided to get_nearby_buses{Style.RESET_ALL}")

        return result

    async def fetch_stop_data(self, stop_id: str) -> Optional[Dict[str, Any]]:
        """Fetch stop data from GTFS and 511 API."""
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
                print(f"{Fore.BLUE}ℹ️ Fetching real-time data for stop {stop_id}{Style.RESET_ALL}")
                response = requests.get(url, params=params)
                response.raise_for_status()

                content = response.content.decode('utf-8-sig')
                data = json.loads(content)

                delivery = data.get("ServiceDelivery", {})
                monitoring = delivery.get("StopMonitoringDelivery", {})
                stops = monitoring.get("MonitoredStopVisit", [])

                if not stops:
                    print(f"{Fore.YELLOW}⚠️ No real-time data found for stop {stop_id}, using static schedule{Style.RESET_ALL}")
                    return static_schedule

                # Process real-time data
                inbound = []
                outbound = []
                now = datetime.now()

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

                    try:
                        arrival_time = None
                        if expected:
                            # Remove timezone and 'Z' suffix, convert to local time
                            arrival_str = expected.replace('Z', '').split('+')[0]
                            arrival_time = datetime.strptime(arrival_str, "%Y-%m-%dT%H:%M:%S")
                        elif aimed:
                            # Remove timezone and 'Z' suffix, convert to local time
                            arrival_str = aimed.replace('Z', '').split('+')[0]
                            arrival_time = datetime.strptime(arrival_str, "%Y-%m-%dT%H:%M:%S")

                        if not arrival_time:
                            continue

                        # Only show arrivals within next 2 hours
                        time_diff = (arrival_time - now).total_seconds() / 3600
                        if time_diff < 0 or time_diff > 2:
                            continue

                        # Calculate delay
                        delay_minutes = 0
                        if expected and aimed:
                            expected_dt = datetime.strptime(expected.replace('Z', '').split('+')[0], "%Y-%m-%dT%H:%M:%S")
                            aimed_dt = datetime.strptime(aimed.replace('Z', '').split('+')[0], "%Y-%m-%dT%H:%M:%S")
                            delay_minutes = int((expected_dt - aimed_dt).total_seconds() / 60)

                        # Format arrival time
                        arrival_str = arrival_time.strftime("%I:%M %p").lstrip('0')

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
                            'arrival_time': arrival_str,
                            'status': status
                        }

                        # Direction check based on destination and route name
                        route_name = line_name.lower()
                        destination_lower = destination_name.lower()

                        if (any(term in destination_lower for term in ['ocean', 'beach', 'zoo', 'cliff']) or
                            any(term in route_name for term in ['outbound', 'ocean', 'beach', 'zoo']) or
                            direction == "0"):
                            outbound.append(bus_info)
                        elif (any(term in destination_lower for term in ['downtown', 'market', 'ferry', 'transit center', 'terminal']) or
                            any(term in route_name for term in ['inbound', 'downtown', 'market', 'ferry']) or
                            direction == "1"):
                            inbound.append(bus_info)
                        else:
                            if direction == "0":
                                outbound.append(bus_info)
                            else:
                                inbound.append(bus_info)

                    except ValueError as e:
                        print(f"{Fore.YELLOW}⚠️ Error parsing time for stop {stop_id}: {e}{Style.RESET_ALL}")
                        continue

                # Sort arrivals and limit
                inbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
                outbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))

                return {
                    'inbound': inbound[:2],
                    'outbound': outbound[:2]
                }

            except Exception as e:
                print(f"{Fore.RED}✗ Error fetching real-time data: {str(e)}{Style.RESET_ALL}")
                return static_schedule

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
        try:
            # Try real-time data first
            real_time_data = await self.fetch_stop_data(stop_id)
            if real_time_data and (real_time_data['inbound'] or real_time_data['outbound']):
                return real_time_data

            # Fall back to static GTFS data
            return self._get_static_schedule(stop_id)

        except Exception as e:
            print(f"{Fore.RED}✗ Error fetching schedule for stop {stop_id}: {e}{Style.RESET_ALL}")
            return None

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
        data = await self.get_stop_schedule(stop_id) # Use get_stop_schedule
        if not data:
            return None

        result = {}

        if direction in ["both", "inbound"]:
            result["inbound"] = data["inbound"][:limit]
        if direction in ["both", "outbound"]:
            result["outbound"] = data["outbound"][:limit]

        return result