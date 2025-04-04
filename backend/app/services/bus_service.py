import os
import sys
import httpx # Asynchronous HTTP client
import json
import pandas as pd
import math
from redis import Redis, RedisError # Import RedisError for specific handling
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone # Added timezone

# --- Configuration Loading ---
try:
    # Adjust this path based on your actual project structure
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from app.config import settings # Now import settings
except ImportError as e:
    print(f"[ERROR] Failed to import settings. Check PYTHONPATH or run location. Error: {e}")
    # Fallback settings for demonstration if import fails
    class PlaceholderSettings:
        API_KEY = "YOUR_FALLBACK_511_API_KEY" # Use your actual key here or in .env
        REDIS_HOST = "localhost"
        REDIS_PORT = 6379
        GTFS_PATHS = {"muni": "gtfs_data/muni_gtfs-current"} # Example path
        
        # Fix the unused parameter warning by prefixing with underscore
        def get_gtfs_data(self, _agency): 
            """
            Placeholder method that returns empty DataFrames.
            The _agency parameter is unused intentionally.
            """
            return (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    settings = PlaceholderSettings()
    print("[WARN] Using placeholder settings due to import error.")


# --- Constants ---
API_BASE_URL = "http://api.511.org/transit"
CACHE_TTL_REALTIME = 60  # Cache real-time data for 60 seconds
CACHE_TTL_STATIC = 300 # Cache static data for 5 minutes (adjust as needed)
CACHE_TTL_EMPTY = 120  # Cache empty results for 2 minutes

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
except RedisError as e: # Catch specific Redis errors
    print(f"[ERROR] Redis connection/ping failed: {e}. Caching will be disabled.")
    redis_cache = None
except Exception as e: # Catch other potential errors like configuration issues
     print(f"[ERROR] Failed to initialize Redis connection: {e}. Caching will be disabled.")
     redis_cache = None

# --- BusService Class ---
class BusService:
    """
    Service class for fetching and processing bus stop/schedule information.
    Combines GTFS static data with 511 real-time API data and Redis caching.
    """
    def __init__(self):
        """Initializes the BusService, loading configurations and GTFS data."""
        print("[INFO] Initializing BusService...")
        self.api_key: Optional[str] = settings.API_KEY
        self.base_url: str = API_BASE_URL
        self.gtfs_data: Dict[str, pd.DataFrame] = {}
        self._stops_dict_cache: Optional[Dict[str, Dict]] = None # Cache for stop lookups

        if not self.api_key:
             print("[WARN] 511.org API Key (API_KEY) not found or empty in settings.")

        # Load GTFS data
        try:
            agency_key = "muni" # Assuming Muni for this instance
            gtfs_tuple: Tuple[pd.DataFrame, ...] = settings.get_gtfs_data(agency_key)
            df_keys = ['routes', 'trips', 'stops', 'stop_times', 'calendar']

            if len(gtfs_tuple) != len(df_keys):
                 raise ValueError(f"Expected {len(df_keys)} GTFS DataFrames, got {len(gtfs_tuple)}")

            for key, df in zip(df_keys, gtfs_tuple):
                 self.gtfs_data[key] = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
                 if self.gtfs_data[key].empty: print(f"[WARN] GTFS data for '{key}' is empty.")
                 else: print(f"[INFO] Loaded GTFS '{key}' data: {len(df)} rows.")

            self._preprocess_gtfs() # Perform pre-processing after loading
            print("[INFO] BusService initialized successfully.")

        except Exception as e:
             print(f"[ERROR] Failed to initialize BusService or load/process GTFS data: {e}")
             # Ensure gtfs_data is initialized even on failure
             self.gtfs_data = {key: pd.DataFrame() for key in df_keys}


        # Create httpx AsyncClient instance for reuse
        self.http_client: httpx.AsyncClient = httpx.AsyncClient(
             timeout=9.0, # Slightly less than typical frontend timeouts
             limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
             follow_redirects=True
        )

    def _preprocess_gtfs(self):
        """Performs pre-processing on loaded GTFS DataFrames."""
        print("[DEBUG] Pre-processing GTFS data...")
        # Stops Pre-processing
        if 'stops' in self.gtfs_data and not self.gtfs_data['stops'].empty:
            stops_df = self.gtfs_data['stops']
            stops_df['stop_lat'] = pd.to_numeric(stops_df['stop_lat'], errors='coerce')
            stops_df['stop_lon'] = pd.to_numeric(stops_df['stop_lon'], errors='coerce')
            original_len = len(stops_df)
            stops_df.dropna(subset=['stop_lat', 'stop_lon'], inplace=True)
            if len(stops_df) < original_len: print(f"[WARN] Dropped {original_len - len(stops_df)} stops due to invalid coordinates.")
            stops_df['stop_id'] = stops_df['stop_id'].astype(str)
            self._build_stops_dict_cache()

        # Calendar Pre-processing
        if 'calendar' in self.gtfs_data and not self.gtfs_data['calendar'].empty:
            calendar_df = self.gtfs_data['calendar']
            date_cols = ['start_date', 'end_date']
            day_cols = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            for col in date_cols:
                 if col in calendar_df.columns:
                      # Store both int and original string if needed elsewhere
                      calendar_df[f'{col}_int'] = pd.to_numeric(calendar_df[col], errors='coerce')
                 else: print(f"[WARN] Calendar date column '{col}' not found.")
            for col in day_cols:
                 if col in calendar_df.columns:
                      calendar_df[col] = pd.to_numeric(calendar_df[col], errors='coerce').fillna(0).astype(int)
                 else: print(f"[WARN] Calendar day column '{col}' not found.")
            # Ensure service_id is string for consistent joins/lookups
            if 'service_id' in calendar_df.columns:
                calendar_df['service_id'] = calendar_df['service_id'].astype(str)

        # Ensure key columns in other DFs are strings for consistent joins
        for df_name, key_cols in [('trips', ['trip_id', 'route_id', 'service_id']),
                                  ('stop_times', ['trip_id', 'stop_id']),
                                  ('routes', ['route_id'])]:
             if df_name in self.gtfs_data and not self.gtfs_data[df_name].empty:
                  df = self.gtfs_data[df_name]
                  for col in key_cols:
                       if col in df.columns:
                           df[col] = df[col].astype(str)

        print("[DEBUG] GTFS pre-processing finished.")


    def _build_stops_dict_cache(self):
         """Builds a dictionary cache (stop_id -> stop_data) for faster lookups."""
         if 'stops' in self.gtfs_data and not self.gtfs_data['stops'].empty:
              print("[DEBUG] Building stops dictionary cache...")
              try:
                   # Use correct columns after pre-processing
                   self._stops_dict_cache = self.gtfs_data['stops'].set_index('stop_id').to_dict('index')
                   print(f"[DEBUG] Built stops cache with {len(self._stops_dict_cache)} entries.")
              except Exception as e:
                   print(f"[ERROR] Failed to build stops dictionary cache: {e}")
                   self._stops_dict_cache = {}
         else:
             self._stops_dict_cache = {}

    def _get_stop_details(self, stop_id: str) -> Optional[Dict]:
         """Gets stop details (name, lat, lon) from the cache or DataFrame."""
         stop_id_str = str(stop_id)
         if self._stops_dict_cache: # Check if cache exists
              return self._stops_dict_cache.get(stop_id_str)

         # Fallback if cache isn't built
         if 'stops' in self.gtfs_data and not self.gtfs_data['stops'].empty:
              stop_series = self.gtfs_data['stops'][self.gtfs_data['stops']['stop_id'] == stop_id_str]
              if not stop_series.empty:
                   return stop_series.iloc[0].to_dict()
         return None


    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculates Haversine distance between two points in miles."""
        if None in [lat1, lon1, lat2, lon2] or not all(isinstance(n, (int, float)) for n in [lat1, lon1, lat2, lon2]):
            return float('inf') # Handle non-numeric or None inputs

        R = 3959  # Earth radius in miles
        try:
            lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(math.radians, [lat1, lon1, lat2, lon2])
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad
            a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
            c = 2 * math.asin(math.sqrt(a))
            return R * c
        except (ValueError, TypeError) as e:
            print(f"[WARN _calculate_distance] Error: {e}")
            return float('inf')


    async def find_nearby_stops(self, lat: float, lon: float, radius_miles: float = 0.15, limit: int = 10) -> List[Dict[str, Any]]:
        """Finds nearby stops using the pre-loaded GTFS stops DataFrame."""
        stops_df = self.gtfs_data.get('stops')
        if stops_df is None or stops_df.empty:
            print("[ERROR find_nearby_stops] Stops GTFS data not available.")
            return []

        print(f"[DEBUG find_nearby_stops] Finding stops near ({lat}, {lon}), radius: {radius_miles} miles, limit: {limit}")
        nearby_stops = []

        # Use vectorized calculation if possible, otherwise iterate
        # Iteration shown here for clarity and compatibility with error handling
        for index, stop in stops_df.iterrows():
            stop_id = stop.get('stop_id') # Already string
            stop_lat = stop.get('stop_lat') # Already float/NaN
            stop_lon = stop.get('stop_lon') # Already float/NaN

            if pd.isna(stop_lat) or pd.isna(stop_lon) or not stop_id:
                continue

            distance = self._calculate_distance(lat, lon, stop_lat, stop_lon)

            if distance <= radius_miles:
                route_info = self._get_routes_for_stop(stop_id) # Use helper function

                nearby_stops.append({
                    'stop_id': stop_id,
                    'stop_name': stop.get('stop_name', 'Unknown Name'),
                    'stop_lat': stop_lat,
                    'stop_lon': stop_lon,
                    'distance_miles': round(distance, 2),
                    'routes': route_info # Attach route info
                })

        nearby_stops.sort(key=lambda x: x['distance_miles'])
        print(f"[DEBUG find_nearby_stops] Found {len(nearby_stops)} stops within radius before limit.")
        return nearby_stops[:limit]

    def _get_routes_for_stop(self, stop_id: str) -> List[Dict[str, str]]:
        """Helper to get distinct routes serving a specific stop from GTFS DataFrames."""
        route_info_list = []
        stop_id_str = str(stop_id)
        try:
             # Check if necessary GTFS data exists
             if all(df in self.gtfs_data and not self.gtfs_data[df].empty for df in ['stop_times', 'trips', 'routes']):
                  stop_times_df = self.gtfs_data['stop_times']
                  trips_df = self.gtfs_data['trips']
                  routes_df = self.gtfs_data['routes']

                  relevant_stop_times = stop_times_df[stop_times_df['stop_id'] == stop_id_str]
                  if not relevant_stop_times.empty:
                       relevant_trip_ids = relevant_stop_times['trip_id'].unique()
                       relevant_trips = trips_df[trips_df['trip_id'].isin(relevant_trip_ids)]
                       if not relevant_trips.empty:
                            relevant_route_ids = relevant_trips['route_id'].unique()
                            relevant_routes = routes_df[routes_df['route_id'].isin(relevant_route_ids)]

                            for _, route in relevant_routes.iterrows():
                                 destination = route.get('route_long_name', '')
                                 if isinstance(destination, str) and ' - ' in destination:
                                      destination = destination.split(' - ')[-1]

                                 route_info_list.append({
                                      'route_id': str(route.get('route_id', '')),
                                      'route_number': str(route.get('route_short_name', '')),
                                      'destination': destination
                                 })
        except Exception as e:
             print(f"[ERROR _get_routes_for_stop] Error getting route info for stop {stop_id_str}: {e}")
        return route_info_list


    async def fetch_real_time_stop_data(self, stop_id: str) -> Optional[Dict[str, Any]]:
        """Fetches ONLY real-time data from 511 StopMonitoring API asynchronously."""
        # ... (Keep the implementation from the previous corrected version) ...
        # Including: api_key check, url/params setup, httpx request, error handling,
        # JSON parsing (with BOM handling), data processing loop, time filtering,
        # status calculation, direction logic, sorting, limiting, and returning dict or None.
        if not self.api_key:
             print("[WARN fetch_real_time] No API key configured.")
             return None
        url = f"{self.base_url}/StopMonitoring"
        params = {"api_key": self.api_key, "agency": "SF", "stopCode": str(stop_id), "format": "json"}
        print(f"[DEBUG fetch_real_time] Requesting URL: {url} with params: {params}")
        try:
            response = await self.http_client.get(url, params=params)
            print(f"[DEBUG fetch_real_time] Response Status: {response.status_code}")
            response.raise_for_status()
            try: data = response.json()
            except json.JSONDecodeError:
                cleaned_text = response.text.encode().decode('utf-8-sig')
                data = json.loads(cleaned_text)
            delivery = data.get("ServiceDelivery", {})
            monitoring = delivery.get("StopMonitoringDelivery", {})
            if isinstance(monitoring, list): monitoring = monitoring[0] if monitoring else {}
            stops = monitoring.get("MonitoredStopVisit", [])
            if not stops: return {'inbound': [], 'outbound': []} # Success but no data

            inbound, outbound = [], []
            now_utc = datetime.now(timezone.utc)
            routes_df = self.gtfs_data.get('routes')
            for stop_visit in stops:
                 # ... (Keep the detailed processing loop from the previous version) ...
                 # This includes extracting journey, line_ref, direction, destination, times,
                 # parsing times to UTC, filtering by 2-hour window, calculating status,
                 # formatting bus_info, and applying direction logic.
                 # Example Snippet (ensure full loop is present):
                 journey = stop_visit.get("MonitoredVehicleJourney", {})
                 line_ref_raw = journey.get("LineRef")
                 if not line_ref_raw: continue
                 line_ref = str(line_ref_raw).split(':')[-1]
                 # ... (get route_number, line_name from GTFS routes_df) ...
                 call = journey.get("MonitoredCall", {})
                 arrival_iso = call.get("ExpectedArrivalTime") or call.get("AimedArrivalTime")
                 if not arrival_iso: continue
                 try: # Parse time to UTC
                     if arrival_iso.endswith('Z'): arrival_time_utc = datetime.fromisoformat(arrival_iso.replace('Z', '+00:00'))
                     elif '+' in arrival_iso or '-' in arrival_iso[10:]: arrival_time_utc = datetime.fromisoformat(arrival_iso)
                     else: arrival_time_utc = datetime.fromisoformat(arrival_iso + '+00:00')
                 except ValueError: continue
                 time_diff_seconds = (arrival_time_utc - now_utc).total_seconds()
                 if time_diff_seconds < -60 or time_diff_seconds > (2 * 3600): continue
                 # ... (calculate status using aimed/expected) ...
                 status = "On Time" # Placeholder
                 arrival_display_time = arrival_time_utc.strftime("%I:%M %p").lstrip('0')
                 bus_info = {'route_number': route_number, 'destination': destination_name, 'arrival_time': arrival_display_time, 'status': status}
                 # ... (apply direction logic to append bus_info to inbound/outbound) ...

            inbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            outbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            return {'inbound': inbound[:2], 'outbound': outbound[:2]}

        except httpx.HTTPStatusError as e: print(f"[ERROR fetch_real_time] HTTP error for stop {stop_id}: {e.response.status_code} - {e}"); return None
        except httpx.TimeoutException: print(f"[ERROR fetch_real_time] Timeout for stop {stop_id}"); return None
        except httpx.RequestError as e: print(f"[ERROR fetch_real_time] Request error for stop {stop_id}: {e}"); return None
        except json.JSONDecodeError as e: print(f"[ERROR fetch_real_time] JSON decode error for stop {stop_id}: {e}"); return None
        except Exception as e: print(f"[ERROR fetch_real_time] Unexpected error for stop {stop_id}: {e}"); return None


    def _get_static_schedule(self, stop_id: str) -> Optional[Dict[str, Any]]:
        """
        Gets the static schedule from pre-loaded GTFS DataFrames for a specific stop.
        Replace the placeholder logic with your actual efficient Pandas implementation.
        """
        print(f"[DEBUG _get_static_schedule] Getting static schedule for stop {stop_id} using Pandas")
        stop_id_str = str(stop_id)

        # --- !!! IMPORTANT: Replace placeholder with your ACTUAL Pandas logic !!! ---
        # --- This placeholder returns minimal data for testing purposes ---
        try:
            # 1. Check data availability
            required_dfs = ['stops', 'stop_times', 'trips', 'routes', 'calendar']
            if any(df not in self.gtfs_data or self.gtfs_data[df].empty for df in required_dfs):
                 print(f"[WARN _get_static_schedule] Missing GTFS data.")
                 return {'inbound': [], 'outbound': []}

            # 2. Check if stop exists
            stops_df = self.gtfs_data['stops']
            if stops_df[stops_df['stop_id'] == stop_id_str].empty:
                 print(f"[WARN _get_static_schedule] Stop ID {stop_id_str} not found.")
                 return {'inbound': [], 'outbound': []}

            # --- Start of Placeholder Logic ---
            print(f"[INFO _get_static_schedule] Using PLACEHOLDER static schedule logic for stop {stop_id_str}")
            now = datetime.now()
            static_inbound = []
            static_outbound = []
            # Add some dummy data if it's a known test ID, otherwise empty
            if stop_id_str == '123': # Example
                 static_inbound.append({'route_number': 'S1', 'destination': 'Static Downtown', 'arrival_time': (now + timedelta(minutes=45)).strftime("%I:%M %p").lstrip('0'), 'status': 'Scheduled'})
                 static_outbound.append({'route_number': 'S1', 'destination': 'Static Beach', 'arrival_time': (now + timedelta(minutes=75)).strftime("%I:%M %p").lstrip('0'), 'status': 'Scheduled'})
            # --- End of Placeholder Logic ---

            print(f"[DEBUG _get_static_schedule] Finished static schedule for stop {stop_id_str}")
            return {'inbound': static_inbound[:2], 'outbound': static_outbound[:2]}

        except Exception as e:
            print(f"[ERROR _get_static_schedule] Error calculating static schedule for stop {stop_id}: {e}")
            return None # Indicate failure


    async def get_stop_schedule(self, stop_id: str) -> Dict[str, Any]:
        """
        Orchestrates getting the schedule: Cache -> Real-time API -> Static GTFS Fallback.
        Always returns a dictionary {'inbound': [...], 'outbound': [...]}.
        """
        # ... (Keep the implementation from the previous corrected version) ...
        # Including: cache_key, default_empty_schedule, Redis GET, await fetch_real_time,
        # fallback logic calling _get_static_schedule, Redis SETEX, return dict.
        stop_id_str = str(stop_id)
        cache_key = f"stop_schedule:{stop_id_str}"
        default_empty_schedule = {'inbound': [], 'outbound': []}
        cached_data_str: Optional[str] = None

        # 1. Check Cache
        if redis_cache:
            try:
                cached_data_str = redis_cache.get(cache_key)
                if cached_data_str:
                    print(f"[CACHE HIT] Returning cached schedule for stop {stop_id_str}")
                    try: return json.loads(cached_data_str)
                    except json.JSONDecodeError as jde: print(f"[ERROR] Corrupt cache JSON: {jde}")
            except RedisError as e: print(f"[ERROR] Redis GET failed: {e}")
        else: print("[WARN] Redis unavailable, skipping cache check.")

        print(f"[CACHE MISS/SKIP] Fetching data for stop {stop_id_str}...")

        # 2. Try Real-time Data
        schedule_data = await self.fetch_real_time_stop_data(stop_id_str)
        source = "Real-time"
        ttl = CACHE_TTL_REALTIME

        # 3. Fallback to Static GTFS
        is_real_time_failed_or_empty = schedule_data is None or \
                                       (not schedule_data.get('inbound') and not schedule_data.get('outbound'))

        if is_real_time_failed_or_empty:
            log_msg = "FAILED" if schedule_data is None else "EMPTY"
            print(f"[INFO] Real-time data {log_msg} for stop {stop_id_str}, falling back to static...")
            schedule_data = self._get_static_schedule(stop_id_str) # Sync call
            source = "Static GTFS"
            ttl = CACHE_TTL_STATIC
            is_static_failed_or_empty = schedule_data is None or \
                                        (not schedule_data.get('inbound') and not schedule_data.get('outbound'))
            if is_static_failed_or_empty:
                 log_msg_static = "FAILED" if schedule_data is None else "EMPTY"
                 print(f"[WARN] Static schedule {log_msg_static} for stop {stop_id_str}.")
                 schedule_data = default_empty_schedule # Use default empty
                 source = "None (Default Empty)"
                 ttl = CACHE_TTL_EMPTY

        # 4. Cache the final result (ensure it's not None before caching)
        if redis_cache and schedule_data is not None:
            try:
                schedule_json = json.dumps(schedule_data)
                redis_cache.setex(cache_key, ttl, schedule_json)
                print(f"[CACHE SET] Cached schedule for stop {stop_id_str} from {source} with TTL {ttl}s.")
            except TypeError as te: print(f"[ERROR] Failed to serialize schedule data to JSON: {te}.")
            except RedisError as e: print(f"[ERROR] Redis SETEX failed: {e}")
            except Exception as e: print(f"[ERROR] Unexpected caching error: {e}")

        print(f"[DEBUG get_stop_schedule] Returning schedule for stop {stop_id_str} (Source: {source})")
        # Ensure we always return a valid dictionary
        return schedule_data if schedule_data is not None else default_empty_schedule


    async def close(self):
        """Closes the HTTPX client gracefully."""
        if hasattr(self, 'http_client') and self.http_client:
            try:
                await self.http_client.aclose()
                print("[INFO] HTTPX client closed.")
            except Exception as e:
                 print(f"[ERROR] Error closing HTTPX client: {e}")