import os
import sys
import httpx # Asynchronous HTTP client
import json
import pandas as pd
import math
import redis
from redis import Redis
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timezone # Added timezone

def __init__(self, db=None):
    self.db = db  


# --- Configuration Loading ---
# Ensure the app directory is correctly added to the path
# This assumes the script is run from a location where this relative path makes sense
# or that the main FastAPI app handles path setup.
try:
    # Adjust this path based on your actual project structure
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from app.config import settings # Now import settings
except ImportError as e:
    print(f"[ERROR] Failed to import settings. Ensure PYTHONPATH is correct or script is run from project root. Error: {e}")
    # Fallback or raise error depending on requirements
    # For demonstration, using placeholder values if settings fail
    class PlaceholderSettings:
        API_KEY = "YOUR_FALLBACK_API_KEY"
        REDIS_HOST = "localhost"
        REDIS_PORT = 6379
        GTFS_PATHS = {"muni": "gtfs_data/muni_gtfs-current"} # Example path
        def get_gtfs_data(self, agency): return (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()) # Empty DFs
    settings = PlaceholderSettings()
    print("[WARN] Using placeholder settings due to import error.")


# --- Constants ---
API_BASE_URL = "http://api.511.org/transit"
# Define constants for cache TTL (Time-To-Live) in seconds
CACHE_TTL_REALTIME = 60  # Cache real-time data for 60 seconds
CACHE_TTL_STATIC = 300 # Cache static data for 5 minutes
CACHE_TTL_EMPTY = 120  # Cache empty results for 2 minutes to reduce load

# --- Redis Connection ---
redis_cache: Optional[Redis] = None
try:
    # Use settings for Redis connection details
    redis_cache = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True, # Automatically decode responses to strings
        socket_connect_timeout=2, # Timeout for initial connection
        socket_timeout=2 # Timeout for operations
    )
    redis_cache.ping() # Check connection
    print(f"[INFO] Redis connection successful to {settings.REDIS_HOST}:{settings.REDIS_PORT}")
except Exception as e:
    print(f"[ERROR] Redis connection failed: {e}. Caching will be disabled.")
    redis_cache = None # Disable caching if connection fails

# --- BusService Class ---
class BusService:
    """
    Service class to handle fetching and processing bus stop and schedule information,
    integrating GTFS static data with 511 real-time API data and Redis caching.
    """
    def __init__(self, db=None):
        self.db = db
        """Initializes the BusService, loading configurations and GTFS data."""
        print("[INFO] Initializing BusService...")
        self.api_key: Optional[str] = settings.API_KEY
        self.base_url: str = API_BASE_URL
        self.gtfs_data: Dict[str, pd.DataFrame] = {}
        self._stops_dict_cache: Optional[Dict[str, Dict]] = None # Cache for quick stop lookups by ID
        
        # Add this line inside __init__, not at class level
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST, 
            port=settings.REDIS_PORT, 
            decode_responses=True
        )

        if not self.api_key:
             print("[WARN] 511.org API Key (API_KEY) not found in settings.")

        # Load GTFS data for the primary agency (e.g., "muni")
        # This assumes settings.get_gtfs_data handles file loading
        try:
            agency_key = "muni" # Or derive from settings if needed
            gtfs_tuple: Tuple[pd.DataFrame, ...] = settings.get_gtfs_data(agency_key)
            df_keys = ['routes', 'trips', 'stops', 'stop_times', 'calendar']

            if len(gtfs_tuple) != len(df_keys):
                 print(f"[ERROR] Expected {len(df_keys)} GTFS DataFrames from settings.get_gtfs_data, got {len(gtfs_tuple)}")
                 raise ValueError("Incorrect number of DataFrames returned by get_gtfs_data")

            for key, df in zip(df_keys, gtfs_tuple):
                 if not isinstance(df, pd.DataFrame):
                      print(f"[WARN] GTFS data for '{key}' is not a DataFrame. Type: {type(df)}")
                      self.gtfs_data[key] = pd.DataFrame() # Assign empty DataFrame
                 else:
                     self.gtfs_data[key] = df
                     print(f"[INFO] Loaded GTFS '{key}' data: {len(df)} rows.")
                 # Basic validation
                 if df.empty:
                     print(f"[WARN] GTFS data for '{key}' is empty.")

            # --- Pre-process Stops Data ---
            # Convert stop coordinates to numeric, handling errors
            if 'stops' in self.gtfs_data and not self.gtfs_data['stops'].empty:
                stops_df = self.gtfs_data['stops']
                stops_df['stop_lat'] = pd.to_numeric(stops_df['stop_lat'], errors='coerce')
                stops_df['stop_lon'] = pd.to_numeric(stops_df['stop_lon'], errors='coerce')
                # Drop rows where conversion failed
                original_len = len(stops_df)
                stops_df.dropna(subset=['stop_lat', 'stop_lon'], inplace=True)
                if len(stops_df) < original_len:
                    print(f"[WARN] Dropped {original_len - len(stops_df)} stops due to invalid coordinates.")
                # Ensure stop_id is string
                stops_df['stop_id'] = stops_df['stop_id'].astype(str)
                self._build_stops_dict_cache() # Build the lookup cache

            print("[INFO] BusService initialized successfully.")

        except Exception as e:
             print(f"[ERROR] Failed to initialize BusService or load GTFS data: {e}")
             # Depending on severity, you might want to raise the exception
             # raise RuntimeError(f"BusService initialization failed: {e}") from e
             # For now, allow initialization but with potentially missing data
             self.gtfs_data = {key: pd.DataFrame() for key in df_keys}


        # Create an httpx AsyncClient instance for reuse (better performance & connection pooling)
        # Timeout slightly less than frontend timeout (e.g., 10s in frontend -> 9s here)
        self.http_client: httpx.AsyncClient = httpx.AsyncClient(
             timeout=9.0,
             limits=httpx.Limits(max_connections=100, max_keepalive_connections=20), # Adjust limits as needed
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


    async def find_nearby_stops(self, lat: float, lon: float, radius_miles: float = 0.15, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Finds nearby transit stops within a specified radius and limit, including basic route info.
        Uses the pre-loaded GTFS stops DataFrame.
        """
        if 'stops' not in self.gtfs_data or self.gtfs_data['stops'].empty:
            print("[ERROR find_nearby_stops] Stops GTFS data not available.")
            return []

        print(f"[DEBUG find_nearby_stops] Finding stops near ({lat}, {lon}), radius: {radius_miles} miles, limit: {limit}")
        stops_df = self.gtfs_data['stops'] # Use the pre-processed DataFrame
        nearby_stops = []

        # Iterate through stops DataFrame (ensure lat/lon columns are numeric)
        for index, stop in stops_df.iterrows():
            stop_lat = stop.get('stop_lat')
            stop_lon = stop.get('stop_lon')
            stop_id = str(stop.get('stop_id', '')) # Ensure string ID

            if pd.isna(stop_lat) or pd.isna(stop_lon) or not stop_id:
                continue # Skip stops with invalid data

            distance = self._calculate_distance(lat, lon, stop_lat, stop_lon)

            if distance <= radius_miles:
                route_info = []
                # --- Safely get route info ---
                try:
                     # Check if necessary GTFS data exists
                     if all(df in self.gtfs_data and not self.gtfs_data[df].empty for df in ['stop_times', 'trips', 'routes']):
                          stop_times_df = self.gtfs_data['stop_times']
                          trips_df = self.gtfs_data['trips']
                          routes_df = self.gtfs_data['routes']

                          # Find stop_times for this stop
                          relevant_stop_times = stop_times_df[stop_times_df['stop_id'] == stop_id]

                          if not relevant_stop_times.empty:
                               # Find unique trips associated with these stop_times
                               relevant_trip_ids = relevant_stop_times['trip_id'].unique()
                               relevant_trips = trips_df[trips_df['trip_id'].isin(relevant_trip_ids)]

                               if not relevant_trips.empty:
                                    # Find unique routes associated with these trips
                                    relevant_route_ids = relevant_trips['route_id'].unique()
                                    relevant_routes = routes_df[routes_df['route_id'].isin(relevant_route_ids)]

                                    for _, route in relevant_routes.iterrows():
                                         destination = route.get('route_long_name', '') # Default destination
                                         if isinstance(destination, str) and ' - ' in destination:
                                              destination = destination.split(' - ')[-1]

                                         route_info.append({
                                              'route_id': str(route.get('route_id', '')),
                                              'route_number': str(route.get('route_short_name', '')),
                                              'destination': destination
                                         })
                except Exception as e:
                     print(f"[ERROR find_nearby_stops] Error getting route info for stop {stop_id}: {e}")
                # --- End route info ---

                nearby_stops.append({
                    'stop_id': stop_id,
                    'stop_name': stop.get('stop_name', 'Unknown Name'),
                    'stop_lat': stop_lat,
                    'stop_lon': stop_lon,
                    'distance_miles': round(distance, 2),
                    'routes': route_info
                })

        # Sort by distance
        nearby_stops.sort(key=lambda x: x['distance_miles'])
        print(f"[DEBUG find_nearby_stops] Found {len(nearby_stops)} stops within radius before limit.")

        # Return limited results
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
        # Use stopCode for SFMTA according to 511 documentation examples
        params = {
            "api_key": self.api_key,
            "agency": "SF",
            "stopCode": stop_id, # Key parameter for SFMTA
            "format": "json"
        }
        print(f"[DEBUG fetch_real_time] Requesting URL: {url} with params: {params}")

        try:
            response = await self.http_client.get(url, params=params)
            print(f"[DEBUG fetch_real_time] Response Status: {response.status_code}")
            response.raise_for_status() # Raise exception for 4xx/5xx errors

            # Handle potential BOM and decode JSON
            try:
                data = response.json()
            except json.JSONDecodeError:
                print("[WARN fetch_real_time] JSON decode error, trying with BOM removal.")
                cleaned_text = response.text.encode().decode('utf-8-sig')
                data = json.loads(cleaned_text)

            delivery = data.get("ServiceDelivery", {})
            monitoring = delivery.get("StopMonitoringDelivery", {})
            # Handle case where StopMonitoringDelivery might be a list (though usually not)
            if isinstance(monitoring, list):
                 monitoring = monitoring[0] if monitoring else {}
            stops = monitoring.get("MonitoredStopVisit", [])

            if not stops:
                print(f"[DEBUG fetch_real_time] No real-time MonitoredStopVisit found for stop {stop_id}")
                return {'inbound': [], 'outbound': []} # Return empty, not None, if API call succeeds but no data

            # Process real-time data
            inbound = []
            outbound = []
            now_utc = datetime.now(timezone.utc) # Use timezone-aware now for comparisons
            routes_df = self.gtfs_data.get('routes')

            for stop_visit in stops:
                journey = stop_visit.get("MonitoredVehicleJourney", {})
                line_ref_raw = journey.get("LineRef")
                if not line_ref_raw: continue

                line_ref = str(line_ref_raw).split(':')[-1]
                direction_ref = journey.get("DirectionRef", "")
                destination_name = journey.get("DestinationName", "") # Usually a string

                # Get GTFS route info
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
                if not arrival_iso: continue

                # Parse timestamp robustly
                try:
                    # Handle 'Z' and timezone offsets
                    if arrival_iso.endswith('Z'):
                        arrival_time_utc = datetime.fromisoformat(arrival_iso.replace('Z', '+00:00'))
                    elif '+' in arrival_iso or '-' in arrival_iso[10:]: # Check for offset sign after date part
                        arrival_time_utc = datetime.fromisoformat(arrival_iso)
                    else: # Assume UTC if no offset provided by API
                         arrival_time_utc = datetime.fromisoformat(arrival_iso + '+00:00')

                except ValueError:
                    print(f"[WARN fetch_real_time] Could not parse arrival time: {arrival_iso}")
                    continue

                # Filter based on time window (compare timezone-aware times)
                time_diff_seconds = (arrival_time_utc - now_utc).total_seconds()
                if time_diff_seconds < -60 or time_diff_seconds > (2 * 3600): # Allow 1 min past, up to 2 hrs ahead
                    continue

                # Calculate status
                status = "On Time"
                delay_minutes = 0
                if expected and aimed:
                    try:
                         # Parse aimed time similarly
                         if aimed.endswith('Z'): aimed_dt_utc = datetime.fromisoformat(aimed.replace('Z', '+00:00'))
                         elif '+' in aimed or '-' in aimed[10:]: aimed_dt_utc = datetime.fromisoformat(aimed)
                         else: aimed_dt_utc = datetime.fromisoformat(aimed + '+00:00')

                         expected_dt_utc = arrival_time_utc
                         delay_seconds = (expected_dt_utc - aimed_dt_utc).total_seconds()
                         delay_minutes = round(delay_seconds / 60) # Round to nearest minute

                         if delay_minutes > 1: status = f"Delayed ({delay_minutes} min)"
                         elif delay_minutes < -1: status = f"Early ({abs(delay_minutes)} min)"
                    except (ValueError, TypeError) as e:
                        print(f"[WARN fetch_real_time] Could not parse aimed time or calculate delay: {e}")

                # Format arrival time for display (e.g., local time) - adjust as needed
                # For simplicity, keeping UTC time formatted
                arrival_display_time = arrival_time_utc.strftime("%I:%M %p").lstrip('0')

                bus_info = {
                    'route_number': route_number,
                    'destination': destination_name,
                    'arrival_time': arrival_display_time, # Consider converting to local time here if needed
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
                      if is_outbound_numeric: outbound.append(bus_info)
                      else: inbound.append(bus_info) # Default to inbound
                # --- End Direction Logic ---

            # Sort and limit results
            inbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))
            outbound.sort(key=lambda x: datetime.strptime(x['arrival_time'], "%I:%M %p"))

            print(f"[DEBUG fetch_real_time] Processed real-time data for stop {stop_id}. Inbound: {len(inbound)}, Outbound: {len(outbound)}")
            return {'inbound': inbound[:2], 'outbound': outbound[:2]}

        except httpx.HTTPStatusError as e:
            # Log specific HTTP errors, especially 404 (stop not found in API) vs 5xx (server error)
            print(f"[ERROR fetch_real_time] HTTP error for stop {stop_id}: {e.response.status_code} - {e}")
            return None # Indicate failure
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
            # import traceback; traceback.print_exc() # Uncomment for detailed debugging
            return None


    def _get_static_schedule(self, stop_id: str) -> Dict[str, Any]:
        """
        Fallback static GTFS schedule using database if real-time fails.
        """
        print(f"[GTFS] Looking up schedule for stop_id: {stop_id}")

        today = datetime.now()
        weekday = today.strftime('%A').lower()

        try:
            # Get active service_ids for today from calendar
            service_ids = self.db.execute(
                f"SELECT service_id FROM calendar WHERE {weekday} = 1"
            ).scalars().all()

            if not service_ids:
                print(f"[GTFS] No active services for {weekday}")
                return {'inbound': [], 'outbound': []}

            # Fetch trips and stop_times for the stop
            query = f"""
            SELECT
                r.route_short_name AS route_number,
                r.route_long_name AS destination,
                st.arrival_time,
                t.direction_id
            FROM stop_times st
            JOIN trips t ON st.trip_id = t.trip_id
            JOIN routes r ON t.route_id = r.route_id
            WHERE st.stop_id = :stop_id
            AND t.service_id = ANY(:service_ids)
            ORDER BY st.arrival_time ASC
            LIMIT 20;
            """
            results = self.db.execute(query, {
                "stop_id": stop_id,
                "service_ids": service_ids
            }).fetchall()

            schedule = defaultdict(list)
            for row in results:
                item = {
                    "route_number": row.route_number,
                    "destination": row.destination,
                    "arrival_time": row.arrival_time,
                    "status": "Scheduled"
                }
                direction = 'inbound' if row.direction_id == 0 else 'outbound'
                schedule[direction].append(item)

            return schedule

        except Exception as e:
            print(f"[ERROR] Static GTFS fallback failed for stop {stop_id}: {e}")
            return {'inbound': [], 'outbound': []}

    async def close(self):
        """Closes the HTTPX client gracefully."""
        if hasattr(self, 'http_client') and self.http_client:
            try:
                await self.http_client.aclose()
                print("[INFO] HTTPX client closed.")
            except Exception as e:
                 print(f"[ERROR] Error closing HTTPX client: {e}")

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