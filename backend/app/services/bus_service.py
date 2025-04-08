import os
import sys
import httpx
import json
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone
from collections import defaultdict
from colorama import init, Fore, Style
from sqlalchemy.orm import Session
from redis import Redis
from fastapi import HTTPException
from sqlalchemy import text 
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.config import settings

try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from app.config import settings
except ImportError as e:
    print(f"[ERROR] Failed to import settings. Ensure PYTHONPATH is correct or script is run from project root. Error: {e}")
    class PlaceholderSettings:
        API_KEY = "YOUR_FALLBACK_API_KEY"
        REDIS_HOST = "localhost"
        REDIS_PORT = 6379
        GTFS_PATHS = {"muni": "gtfs_data/muni_gtfs-current"}
        def get_gtfs_data(self, agency):
            return (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    settings = PlaceholderSettings()
    print("[WARN] Using placeholder settings due to import error.")

# --- Redis Connection ---
redis_cache: Optional[Redis] = None
try:
    redis_cache = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2
    )
    redis_cache.ping()
    print(f"[INFO] Redis connection successful to {settings.REDIS_HOST}:{settings.REDIS_PORT}")
except Exception as e:
    print(f"[ERROR] Redis connection failed: {e}. Caching will be disabled.")
    redis_cache = None

class BusService:
    def __init__(self, db: Session):
        self.db = db
        self.stops_cache = None
        self.api_key = settings.API_KEY
        self.base_url = "http://api.511.org/transit"
        self.gtfs_data: Dict[str, pd.DataFrame] = {}

        try:
            agency_key = "muni"
            gtfs_tuple: Tuple[pd.DataFrame, ...] = settings.get_gtfs_data(agency_key)
            df_keys = ['routes', 'trips', 'stops', 'stop_times', 'calendar']

            if len(gtfs_tuple) != len(df_keys):
                raise ValueError("Incorrect number of DataFrames returned by get_gtfs_data")

            for key, df in zip(df_keys, gtfs_tuple):
                if not isinstance(df, pd.DataFrame):
                    print(f"[WARN] GTFS data for '{key}' is not a DataFrame. Type: {type(df)}")
                    self.gtfs_data[key] = pd.DataFrame()
                else:
                    self.gtfs_data[key] = df
                    print(f"[INFO] Loaded GTFS '{key}' data: {len(df)} rows.")
                if df.empty:
                    print(f"[WARN] GTFS data for '{key}' is empty.")

            if 'stops' in self.gtfs_data and not self.gtfs_data['stops'].empty:
                stops_df = self.gtfs_data['stops']
                stops_df['stop_lat'] = pd.to_numeric(stops_df['stop_lat'], errors='coerce')
                stops_df['stop_lon'] = pd.to_numeric(stops_df['stop_lon'], errors='coerce')
                original_len = len(stops_df)
                stops_df.dropna(subset=['stop_lat', 'stop_lon'], inplace=True)
                if len(stops_df) < original_len:
                    print(f"[WARN] Dropped {original_len - len(stops_df)} stops due to invalid coordinates.")
                stops_df['stop_id'] = stops_df['stop_id'].astype(str)

            print("[INFO] BusService initialized successfully.")

        except Exception as e:
            print(f"[ERROR] Failed to initialize BusService or load GTFS data: {e}")
            self.gtfs_data = {key: pd.DataFrame() for key in ['routes', 'trips', 'stops', 'stop_times', 'calendar']}

        self.http_client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=9.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=True
        )
        
    def _build_stops_dict_cache(self):
         """Builds a dictionary cache for stops for faster lookups."""
         if 'stops' in self.gtfs_data and not self.gtfs_data['stops'].empty:
              print("[DEBUG] Building stops dictionary cache...")
              try:
                   self._stops_dict_cache = self.gtfs_data['stops'].set_index('stop_id').to_dict('index')
                   print(f"[DEBUG] Built stops cache with {len(self._stops_dict_cache)} entries.")
              except Exception as e:
                   print(f"[ERROR] Failed to build stops dictionary cache: {e}")
                   self._stops_dict_cache = {} # Use empty dict on error
         else:
             self._stops_dict_cache = {}

    def _get_stop_details(self, stop_id: str) -> Optional[Dict]:
         """Gets stop details (name, lat, lon) from the cache or DataFrame."""
         if self._stops_dict_cache is not None:
              return self._stops_dict_cache.get(str(stop_id)) # Use cache if available

         # Fallback to DataFrame lookup if cache failed or wasn't built
         if 'stops' in self.gtfs_data and not self.gtfs_data['stops'].empty:
              stop_series = self.gtfs_data['stops'][self.gtfs_data['stops']['stop_id'] == str(stop_id)]
              if not stop_series.empty:
                   return stop_series.iloc[0].to_dict()
         return None


    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.
        Returns distance in miles.
        """
        if None in [lat1, lon1, lat2, lon2]:
            return float('inf') # Return infinity if coordinates are invalid

        R = 3959  # Earth's radius in miles
        try:
            lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(math.radians, [lat1, lon1, lat2, lon2])
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad

            a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
            c = 2 * math.asin(math.sqrt(a))

            return R * c
        except (ValueError, TypeError) as e:
            print(f"[WARN _calculate_distance] Error calculating distance for ({lat1},{lon1}) to ({lat2},{lon2}): {e}")
            return float('inf') # Return infinity on calculation error
        
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

    async def fetch_real_time_stop_data(self, stop_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches ONLY real-time data from 511 StopMonitoring API asynchronously.
        Returns a dictionary {'inbound': [...], 'outbound': [...]} or None on failure.
        """
        if not self.api_key:
            print("[WARN fetch_real_time] No API key configured. Skipping real-time fetch.")
            return None

        url = f"{self.base_url}/StopMonitoring"
        params = {
            "api_key": self.api_key,
            "agency": "SF",
            "stopCode": stop_id,
            "format": "json"
        }
        print(f"[DEBUG fetch_real_time] Requesting URL: {url} with params: {params}")

        try:
            response = await self.http_client.get(url, params=params)
            print(f"[DEBUG fetch_real_time] Response Status: {response.status_code}")
            response.raise_for_status()

            try:
                data = response.json()
            except json.JSONDecodeError:
                print("[WARN fetch_real_time] JSON decode error, trying with BOM removal.")
                cleaned_text = response.text.encode().decode('utf-8-sig')
                data = json.loads(cleaned_text)

            delivery = data.get("ServiceDelivery", {})
            monitoring = delivery.get("StopMonitoringDelivery", {})
            if isinstance(monitoring, list):
                monitoring = monitoring[0] if monitoring else {}
            stops = monitoring.get("MonitoredStopVisit", [])

            if not stops:
                print(f"[DEBUG fetch_real_time] No real-time MonitoredStopVisit found for stop {stop_id}")
                return {'inbound': [], 'outbound': []}

            inbound = []
            outbound = []
            now_utc = datetime.now(timezone.utc)
            routes_df = self.gtfs_data.get('routes')

            for stop_visit in stops:
                journey = stop_visit.get("MonitoredVehicleJourney", {})
                line_ref_raw = journey.get("LineRef")
                if not line_ref_raw:
                    continue

                line_ref = str(line_ref_raw).split(':')[-1]
                direction_ref = journey.get("DirectionRef", "")
                destination_name = journey.get("DestinationName", "")

                route_number = line_ref
                line_name = destination_name
                if routes_df is not None and not routes_df.empty:
                    route_info_series = routes_df[routes_df['route_id'] == line_ref]
                    if not route_info_series.empty:
                        route_info = route_info_series.iloc[0]
                        line_name = route_info.get('route_long_name', line_name)
                        route_number = route_info.get('route_short_name', route_number)

                call = journey.get("MonitoredCall", {})
                expected = call.get("ExpectedArrivalTime")
                aimed = call.get("AimedArrivalTime")
                arrival_iso = expected or aimed
                if not arrival_iso:
                    continue

                try:
                    if arrival_iso.endswith('Z'):
                        arrival_time_utc = datetime.fromisoformat(arrival_iso.replace('Z', '+00:00'))
                    elif '+' in arrival_iso or '-' in arrival_iso[10:]:
                        arrival_time_utc = datetime.fromisoformat(arrival_iso)
                    else:
                        arrival_time_utc = datetime.fromisoformat(arrival_iso + '+00:00')
                except ValueError:
                    print(f"[WARN fetch_real_time] Could not parse arrival time: {arrival_iso}")
                    continue

                time_diff_seconds = (arrival_time_utc - now_utc).total_seconds()
                if time_diff_seconds < -60 or time_diff_seconds > (2 * 3600):
                    continue

                status = "On Time"
                delay_minutes = 0
                if expected and aimed:
                    try:
                        if aimed.endswith('Z'):
                            aimed_dt_utc = datetime.fromisoformat(aimed.replace('Z', '+00:00'))
                        elif '+' in aimed or '-' in aimed[10:]:
                            aimed_dt_utc = datetime.fromisoformat(aimed)
                        else:
                            aimed_dt_utc = datetime.fromisoformat(aimed + '+00:00')

                        expected_dt_utc = arrival_time_utc
                        delay_seconds = (expected_dt_utc - aimed_dt_utc).total_seconds()
                        delay_minutes = round(delay_seconds / 60)

                        if delay_minutes > 1:
                            status = f"Delayed ({delay_minutes} min)"
                        elif delay_minutes < -1:
                            status = f"Early ({abs(delay_minutes)} min)"
                    except (ValueError, TypeError) as e:
                        print(f"[WARN fetch_real_time] Could not parse aimed time or calculate delay: {e}")

                arrival_display_time = arrival_time_utc.strftime("%I:%M %p").lstrip('0')

                bus_info = {
                    'route_number': route_number,
                    'destination': destination_name,
                    'arrival_time': arrival_display_time,
                    'status': status
                }

                route_name_lower = str(line_name).lower()
                destination_lower = str(destination_name).lower()
                is_outbound_numeric = direction_ref == "0"
                is_inbound_numeric = direction_ref == "1"
                is_outbound_keyword = any(term in destination_lower for term in ['ocean', 'beach', 'zoo', 'cliff', 'west portal']) or \
                    any(term in route_name_lower for term in ['outbound'])
                is_inbound_keyword = any(term in destination_lower for term in ['downtown', 'market', 'ferry', 'transit center', 'terminal', 'caltrain', 'embarcadero']) or \
                    any(term in route_name_lower for term in ['inbound'])
                if is_outbound_keyword or (is_outbound_numeric and not is_inbound_keyword):
                    outbound.append(bus_info)
                elif is_inbound_keyword or (is_inbound_numeric and not is_outbound_keyword):
                    inbound.append(bus_info)
                else:
                    if is_outbound_numeric:
                        outbound.append(bus_info)
                    else:
                        inbound.append(bus_info)

            inbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            outbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))

            print(f"[DEBUG fetch_real_time] Processed real-time data for stop {stop_id}. Inbound: {len(inbound)}, Outbound: {len(outbound)}")
            return {'inbound': inbound[:2], 'outbound': outbound[:2]}

        except httpx.HTTPStatusError as e:
            print(f"[ERROR fetch_real_time] HTTP error for stop {stop_id}: {e.response.status_code} - {e}")
            return None
        except httpx.TimeoutException:
            print(f"[ERROR fetch_real_time] Timeout fetching 511 data for stop {stop_id}")
            return None
        except httpx.RequestError as e:
            print(f"[ERROR fetch_real_time] Request error for stop {stop_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"[ERROR fetch_real_time] JSON decode error for stop {stop_id}: {e}")
            return None
        except Exception as e:
            print(f"[ERROR fetch_real_time] Unexpected error processing real-time for stop {stop_id}: {e}")
            return None



    async def get_stop_schedule(self, stop_id: str) -> List[Dict[str, Any]]:

        try:
            # 1. GTFS Schedule
            schedule = await self._get_gtfs_schedule_for_stop(stop_id)
            if not schedule:
                return []

            now = datetime.now().time()

            # 2. Live vehicle positions from 511
            live_vehicles = await self.get_live_bus_positions_async(agency="SF")
            live_stop_ids = {
                v.get("MonitoredVehicleJourney", {}).get("MonitoredCall", {}).get("StopPointRef", "").strip()
                for v in live_vehicles
            }

            upcoming = []
            for item in schedule:
                arr_str = item.get("arrival_time")
                if not arr_str:
                    continue
                try:
                    arr_time = datetime.strptime(arr_str, "%H:%M:%S").time()
                    if arr_time > now:
                        item["status"] = "Live" if str(item.get("stop_id")) in live_stop_ids else "Scheduled"
                        upcoming.append(item)
                except Exception as e:
                    print(f"[WARN] Failed to parse arrival time {arr_str}: {e}")

            return upcoming[:3]

        except Exception as e:
            print(f"[ERROR] get_stop_schedule failed for stop {stop_id}: {e}")
            return []

# --- Potentially add other methods like get_live_bus_positions if needed ---
# Remember to make them async and use self.http_client if they make HTTP requests
# Example:
    async def get_live_bus_positions_async(self, agency: str = "SF", route: str = None) -> List[Dict]:
        """
        Async version to fetch vehicle positions.
        
        Args:
            agency: Transit agency code (SF for SFMTA/Muni, BA for BART, etc)
            route: Optional route number to filter results
        
        Returns:
            List of vehicle position dictionaries with coordinates and metadata
        """
        if not self.api_key: 
            print(f"[WARN] No API key configured. Cannot fetch vehicle positions for agency {agency}.")
            return []
        
        url = f"{self.base_url}/VehicleMonitoring"
        params = {
            "api_key": self.api_key,
            "agency": agency,  # Using the agency parameter correctly
            "format": "json"
        }
        
        # Add route filter if specified
        if route:
            params["line"] = route
        
        try:
            print(f"[DEBUG] Fetching vehicle positions for agency: {agency}{' route: '+route if route else ''}")
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            
            vehicles = await self.fetch_real_time_positions()
            return vehicles
            
        except Exception as e:
            print(f"[ERROR] Unexpected error processing vehicle positions for agency {agency}: {e}")
            return []



# --- Optional: Graceful Shutdown Hook (if running standalone or need cleanup) ---
# import atexit
# bus_service_instance = BusService() # Create instance if needed globally
# async def cleanup():
#    await bus_service_instance.close()
# atexit.register(lambda: asyncio.run(cleanup())) # Requires asyncio context if run standalone