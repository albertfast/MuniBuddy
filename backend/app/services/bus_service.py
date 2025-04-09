import os
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import math
import pandas as pd
from colorama import init, Fore, Style
import json
from app.config import settings
import pytz
import traceback

# Initialize colorama for colored output
init()

load_dotenv()
API_KEY = os.getenv("API_KEY")
AGENCY_IDS = ["SFMTA"]  # Default to SFMTA if not specified


class BusService:
    def __init__(self):
        self.api_key = API_KEY
        self.base_url = "http://api.511.org/transit"
        self.agency_ids = AGENCY_IDS
        self.stops_cache = None
        self.gtfs_data = {}

        # Load GTFS data from settings
        try:
            agency_map = {
                "SFMTA": "muni",
                "MUNI": "muni",
                "SF": "muni",
                "BA": "bart",
                "BART": "bart"
            }
            
            # Load both MUNI and BART data by default
            for agency in ["muni", "bart"]:
                gtfs_data = settings.get_gtfs_data(agency)
                if gtfs_data:
                    routes_df, trips_df, stops_df, stop_times_df, calendar_df = gtfs_data
                    if agency not in self.gtfs_data:
                        self.gtfs_data[agency] = {}
                    self.gtfs_data[agency]['routes'] = routes_df
                    self.gtfs_data[agency]['trips'] = trips_df
                    self.gtfs_data[agency]['stops'] = stops_df
                    self.gtfs_data[agency]['stop_times'] = stop_times_df
                    self.gtfs_data[agency]['calendar'] = calendar_df
                    print(f"[DEBUG] Loaded GTFS data for {agency}")
                else:
                    print(f"{Fore.YELLOW}⚠ No GTFS data found for agency {agency}{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}✗ Error loading GTFS data: {str(e)}{Style.RESET_ALL}")

    def _get_static_schedule(self, stop_id: str) -> Dict[str, Any]:
        """Get static schedule from GTFS data."""
        try:
            # Get current time
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            
            # Determine which agency's GTFS data to use and format stop_id accordingly
            agency = None
            gtfs_stop_id = stop_id
            
            # Try with original stop_id first
            for ag in ["muni", "bart"]:
                if ag in self.gtfs_data and 'stops' in self.gtfs_data[ag]:
                    stops_df = self.gtfs_data[ag]['stops']
                    if not stops_df.empty and stop_id in stops_df['stop_id'].values:
                        agency = ag
                        break
            
            # If not found and it's a short ID, try with prefix for MUNI
            if not agency and len(stop_id) <= 4:
                gtfs_stop_id = f"1{stop_id}"
                if 'muni' in self.gtfs_data and 'stops' in self.gtfs_data['muni']:
                    stops_df = self.gtfs_data['muni']['stops']
                    if not stops_df.empty and gtfs_stop_id in stops_df['stop_id'].values:
                        agency = 'muni'
                        print(f"{Fore.BLUE}ℹ️ Found stop {stop_id} as GTFS stop {gtfs_stop_id}{Style.RESET_ALL}")

            if not agency:
                print(f"{Fore.YELLOW}⚠️ No agency found for stop {stop_id} (tried {gtfs_stop_id}){Style.RESET_ALL}")
                return {'inbound': [], 'outbound': []}

            # Get active services for today
            weekday = now.strftime("%A").lower()
            active_services = self.gtfs_data[agency]['calendar'][
                (self.gtfs_data[agency]['calendar'][weekday] == 1) &
                (pd.to_numeric(self.gtfs_data[agency]['calendar']['start_date']) <= int(now.strftime("%Y%m%d"))) &
                (pd.to_numeric(self.gtfs_data[agency]['calendar']['end_date']) >= int(now.strftime("%Y%m%d")))
            ]['service_id']
            
            # Get trips for active services
            active_trips = self.gtfs_data[agency]['trips'][
                self.gtfs_data[agency]['trips']['service_id'].isin(active_services)
            ]
            
            # Get stop times for this stop
            stop_times = self.gtfs_data[agency]['stop_times'][
                self.gtfs_data[agency]['stop_times']['stop_id'] == gtfs_stop_id
            ]
            
            if stop_times.empty:
                print(f"{Fore.YELLOW}⚠️ No stop times found for stop {gtfs_stop_id} ({agency}){Style.RESET_ALL}")
                return {'inbound': [], 'outbound': []}
            
            # Merge with trips and routes to get valid routes for this stop
            schedule_data = stop_times.merge(
                active_trips[['trip_id', 'route_id', 'direction_id', 'trip_headsign']],
                on='trip_id'
            ).merge(
                self.gtfs_data[agency]['routes'][['route_id', 'route_short_name', 'route_long_name']],
                on='route_id'
            )
            
            if schedule_data.empty:
                print(f"{Fore.YELLOW}⚠️ No schedule data found for stop {gtfs_stop_id} ({agency}){Style.RESET_ALL}")
                return {'inbound': [], 'outbound': []}

            # Get unique valid routes for this stop
            valid_routes = schedule_data[['route_short_name']].drop_duplicates()['route_short_name'].tolist()
            print(f"{Fore.BLUE}ℹ️ Valid routes for stop {gtfs_stop_id}: {valid_routes}{Style.RESET_ALL}")
            
            # Filter schedule data to only include valid routes
            schedule_data = schedule_data[schedule_data['route_short_name'].isin(valid_routes)]
            
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
                direction_id = row['direction_id']
                
                # Use direction_id as primary indicator, then fall back to destination keywords
                if direction_id == 1 or any(term in destination_lower for term in ['downtown', 'market', 'ferry', 'transit center', 'terminal']):
                    inbound.append(bus_info)
                elif direction_id == 0 or any(term in destination_lower for term in ['ocean', 'beach', 'zoo', 'cliff']):
                    outbound.append(bus_info)
                else:
                    # If no clear direction, use route name as final fallback
                    if any(term in route_name for term in ['inbound', 'downtown', 'market', 'ferry']):
                        inbound.append(bus_info)
                    else:
                        outbound.append(bus_info)
            
            # Sort arrivals and limit
            inbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            outbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            
            return {
                'inbound': inbound[:2],
                'outbound': outbound[:2]
            }
            
        except Exception as e:
            print(f"{Fore.RED}✗ Error getting static schedule for stop {stop_id}: {str(e)}{Style.RESET_ALL}")
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
            stops = []
            # Combine stops from both MUNI and BART
            for agency in ["muni", "bart"]:
                if agency in self.gtfs_data and 'stops' in self.gtfs_data[agency]:
                    agency_stops = self.gtfs_data[agency]['stops']
                    if not agency_stops.empty:
                        for _, row in agency_stops.iterrows():
                            stops.append({
                                'stop_id': row['stop_id'],
                                'stop_name': row['stop_name'],
                                'stop_lat': float(row['stop_lat']),
                                'stop_lon': float(row['stop_lon']),
                                'agency': agency
                            })

            if not stops:
                print(f"{Fore.RED}✗ No stops data in GTFS{Style.RESET_ALL}")
                return []

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
                stop_id = stop['stop_id']
                agency = stop.get('agency', 'muni')  # Default to muni if not specified

                try:
                    # For MUNI stops, ensure the stop_id has the correct format (with prefix 1)
                    gtfs_stop_id = stop_id
                    if agency == 'muni' and not stop_id.startswith('1'):
                        gtfs_stop_id = f"1{stop_id}"
                        print(f"{Fore.BLUE}ℹ️ Converting stop ID {stop_id} to GTFS format: {gtfs_stop_id}{Style.RESET_ALL}")

                    # Get stop_times for this stop from the correct agency's GTFS data
                    if agency in self.gtfs_data and 'stop_times' in self.gtfs_data[agency]:
                        stop_times = self.gtfs_data[agency]['stop_times'][
                            self.gtfs_data[agency]['stop_times']['stop_id'] == gtfs_stop_id
                        ]

                        if not stop_times.empty:
                            # Get active services for today
                            weekday = datetime.now().strftime("%A").lower()
                            active_services = self.gtfs_data[agency]['calendar'][
                                (self.gtfs_data[agency]['calendar'][weekday] == 1) &
                                (pd.to_numeric(self.gtfs_data[agency]['calendar']['start_date']) <= int(datetime.now().strftime("%Y%m%d"))) &
                                (pd.to_numeric(self.gtfs_data[agency]['calendar']['end_date']) >= int(datetime.now().strftime("%Y%m%d")))
                            ]['service_id']

                            # Get trips for active services
                            active_trips = self.gtfs_data[agency]['trips'][
                                self.gtfs_data[agency]['trips']['service_id'].isin(active_services)
                            ]

                            # Get valid routes for this stop
                            valid_trips = stop_times.merge(
                                active_trips[['trip_id', 'route_id', 'direction_id']],
                                on='trip_id'
                            )

                            routes = self.gtfs_data[agency]['routes'][
                                self.gtfs_data[agency]['routes']['route_id'].isin(valid_trips['route_id'])
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

                            print(f"{Fore.BLUE}ℹ️ Found {len(route_info)} routes for stop {gtfs_stop_id}: {[r['route_number'] for r in route_info]}{Style.RESET_ALL}")
                        else:
                            route_info = []
                            print(f"{Fore.YELLOW}⚠️ No stop times found for stop {gtfs_stop_id} ({agency}){Style.RESET_ALL}")
                    else:
                        route_info = []

                    stop_info = stop.copy()
                    stop_info['distance_miles'] = round(distance, 2)
                    stop_info['routes'] = route_info
                    stop_info['id'] = stop_id
                    stop_info['stop_id'] = stop_id
                    stop_info['gtfs_stop_id'] = gtfs_stop_id
                    nearby_stops.append(stop_info)

                except KeyError as e:
                    print(f"{Fore.YELLOW}⚠ No route data found for stop {stop_id} ({agency}): {e}{Style.RESET_ALL}")
                    # Still add the stop, just without route information
                    stop_info = stop.copy()
                    stop_info['distance_miles'] = round(distance, 2)
                    stop_info['routes'] = []
                    stop_info['id'] = stop_id
                    stop_info['stop_id'] = stop_id
                    stop_info['gtfs_stop_id'] = gtfs_stop_id if 'gtfs_stop_id' in locals() else stop_id
                    nearby_stops.append(stop_info)
                except Exception as e:
                    print(f"{Fore.RED}✗ Error while processing stop {stop_id} ({agency}): {e}{Style.RESET_ALL}")
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

                        # Calculate minutes until arrival
                        minutes_until = int((arrival_time - now).total_seconds() / 60)

                        # Calculate delay
                        delay_minutes = 0
                        if expected and aimed:
                            expected_dt = datetime.strptime(expected.replace('Z', '').split('+')[0], "%Y-%m-%dT%H:%M:%S")
                            aimed_dt = datetime.strptime(aimed.replace('Z', '').split('+')[0], "%Y-%m-%dT%H:%M:%S")
                            delay_minutes = int((expected_dt - aimed_dt).total_seconds() / 60)

                        # Format arrival time
                        arrival_str = arrival_time.strftime("%I:%M %p").lstrip('0')

                        # Determine status
                        if minutes_until <= 0:
                            status = "Due"
                        elif minutes_until == 1:
                            status = "1 minute"
                        else:
                            status = f"{minutes_until} minutes"

                        if delay_minutes > 0:
                            status += f" (Delayed {delay_minutes} min)"
                        elif delay_minutes < 0:
                            status += f" (Early {abs(delay_minutes)} min)"

                        # Prepare bus information
                        bus_info = {
                            'route_number': route_number,
                            'destination': destination_name,
                            'arrival_time': arrival_str,
                            'status': status,
                            'minutes_until': minutes_until,
                            'is_realtime': True
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

                # Add scheduled arrivals from static schedule
                for direction, arrivals in static_schedule.items():
                    real_time_arrivals = inbound if direction == 'inbound' else outbound
                    real_time_routes = {arr['route_number'] for arr in real_time_arrivals}
                    
                    for arrival in arrivals:
                        # Only add if we don't have real-time data for this route
                        if arrival['route_number'] not in real_time_routes:
                            arrival['is_realtime'] = False
                            if direction == 'inbound':
                                inbound.append(arrival)
                            else:
                                outbound.append(arrival)

                # Sort arrivals by minutes_until for real-time, then by arrival_time for scheduled
                def sort_key(x):
                    if x.get('is_realtime', False):
                        return (0, x.get('minutes_until', float('inf')))
                    return (1, datetime.strptime(x['arrival_time'], "%I:%M %p"))

                inbound.sort(key=sort_key)
                outbound.sort(key=sort_key)

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

    async def get_stop_schedule(self, stop_id: str) -> Dict[str, Any]:
        """Get combined schedule (static + real-time) for a stop."""
        try:
            # Format stop_id for GTFS if necessary
            gtfs_stop_id = stop_id
            if len(stop_id) <= 4 and not stop_id.startswith('1'):
                gtfs_stop_id = f"1{stop_id}"
                print(f"{Fore.YELLOW}Converting stop ID {stop_id} to GTFS format: {gtfs_stop_id}{Style.RESET_ALL}")

            # Use fetch_stop_data which already handles both static and real-time data
            return await self.fetch_stop_data(stop_id)
            
        except Exception as e:
            traceback.print_exc()
            print(f"{Fore.RED}✗ Error getting schedule for stop {stop_id}: {str(e)}{Style.RESET_ALL}")
            return {'inbound': [], 'outbound': []}

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

    async def get_stop_predictions(self, stop_id: str) -> Optional[Dict[str, Any]]:
        """
        Get predictions for a specific stop, combining real-time and static data.
        This is the main method used by the stop-predictions endpoint.
        """
        try:
            # Get real-time data first
            real_time_data = await self.fetch_stop_data(stop_id)
            if real_time_data and (real_time_data.get('inbound') or real_time_data.get('outbound')):
                return real_time_data

            # Fall back to static schedule if no real-time data
            static_schedule = self._get_static_schedule(stop_id)
            return static_schedule

        except Exception as e:
            print(f"{Fore.RED}✗ Error getting predictions for stop {stop_id}: {str(e)}{Style.RESET_ALL}")
            return {'inbound': [], 'outbound': []}

    def _merge_schedule_and_predictions(self, schedule: Dict[str, Any], predictions: Dict[str, Any]) -> Dict[str, Any]:
        """Merge static schedule with real-time predictions."""
        result = {'inbound': [], 'outbound': []}
        
        # Helper function to merge a single direction
        def merge_direction(static_times: List[Dict], real_time_times: List[Dict]) -> List[Dict]:
            merged = []
            
            # Add real-time predictions first
            for pred in real_time_times:
                merged.append({
                    'time': pred['time'],
                    'route': pred.get('route', ''),
                    'is_real_time': True,
                    'vehicle': pred.get('vehicle', ''),
                    'destination': pred.get('destination', '')
                })
            
            # Add static times that don't overlap with real-time predictions
            real_time_routes = {p['route'] for p in real_time_times}
            for static in static_times:
                if static['route'] not in real_time_routes:
                    merged.append({
                        'time': static['time'],
                        'route': static.get('route', ''),
                        'is_real_time': False,
                        'destination': static.get('destination', '')
                    })
            
            # Sort by time
            return sorted(merged, key=lambda x: x['time'])
        
        # Merge both directions
        result['inbound'] = merge_direction(
            schedule.get('inbound', []),
            predictions.get('inbound', [])
        )
        result['outbound'] = merge_direction(
            schedule.get('outbound', []),
            predictions.get('outbound', [])
        )
        
        return result