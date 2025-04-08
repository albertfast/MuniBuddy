# import os
# import sys

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# # Now we can import from app
# from app.db.database import SessionLocal
# from app.services.bus_service import BusService

# # Initialize service with DB
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session
# from redis import Redis
# from typing import Optional
# from math import radians, sin, cos, sqrt, atan2
# import logging
# import requests
# import json
# from datetime import datetime

# from app.db.database import get_db
# from app.models.bus_route import BusRoute
# from app.utils.xml_parser import xml_to_json
# from app.config import settings


# db = SessionLocal()
# bus_service = BusService(db=db)

# # Load GTFS data
# agency_map = {
#     "SFMTA": "muni",
#     "SF": "muni",
#     "BA": "bart",
#     "BART": "bart",
#     "MUNI": "muni"
# }
# normalized_agency = agency_map.get(settings.DEFAULT_AGENCY.upper(), "muni")
# routes_df, trips_df, stops_df, stop_times_df, calendar_df = settings.get_gtfs_data(normalized_agency)

# # Initialize
# logger = logging.getLogger(__name__)
# router = APIRouter()
# redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)

# API_KEY = settings.API_KEY
# AGENCY_ID = settings.AGENCY_ID
# BASE_API_URL = "http://api.511.org/transit"

# # Distance helper
# def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
#     R = 3959.87433
#     lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
#     a = sin((lat2 - lat1)/2)**2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1)/2)**2
#     return R * 2 * atan2(sqrt(a), sqrt(1 - a))

# # ------------------- API ROUTES -------------------
# @router.get("/get-route-details")
# def get_route_details(
#     db: Session = Depends(get_db), 
#     route_short_name: str = Query(..., description="Bus route short name")
# ):
#     route = db.query(BusRoute).filter(BusRoute.route_short_name == route_short_name).first()

#     if route:
#         return {
#             "route_id": route.route_id,
#             "route_name": route.route_name,
#             "origin": route.origin,
#             "destination": route.destination
#         }

#     api_url = f"{BASE_API_URL}/RouteDetails"
#     params = {
#         "api_key": API_KEY,
#         "agency": AGENCY_ID,
#         "route_id": route_short_name,
#         "format": "json"
#     }

#     try:
#         response = requests.get(api_url, params=params, timeout=10)
#         if response.status_code != 200 or not response.content:
#             raise HTTPException(status_code=404, detail="Route not found in GTFS or 511 API")
#         return response.json()
#     except requests.RequestException as e:
#         logger.error(f"511 API request error: {e}")
#         raise HTTPException(status_code=503, detail="511 API unreachable")


# @router.get("/bus-positions")
# def get_bus_positions(bus_number: str, agency: str):
#     """
#     Get real-time position information for buses of a specific route.
#     Uses a three-level approach: 
#     1. Check Redis cache
#     2. Check database GTFS data for static schedule (fallback)
#     3. Call 511 API for real-time data
#     """
#     # First try cache
#     cache_key = f"bus:positions:{agency}:{bus_number}"
#     try:
#         cached_data = redis.get(cache_key)
#         if cached_data:
#             logger.info(f"Cache hit for {cache_key}")
#             return json.loads(cached_data)
#     except Exception as e:
#         logger.warning(f"Redis cache read error: {e}")
    
#     # Cache miss, try to get real-time data
#     try:
#         # Check if we have a BusService method we can use
#         if hasattr(bus_service, 'get_live_bus_positions_async'):
#             # Use the async version but run it synchronously
#             import asyncio
#             loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(loop)
#             try:
#                 buses = loop.run_until_complete(
#                     bus_service.get_live_bus_positions_async(agency, bus_number)
#                 )
#                 loop.close()
                
#                 # Format the data to match our expected output
#                 bus_positions = []
#                 for bus in buses:
#                     bus_positions.append({
#                         "bus_number": bus.get("route", ""),
#                         "current_stop": bus.get("next_stop", {}).get("name", "Unknown"),
#                         "latitude": bus.get("lat"),
#                         "longitude": bus.get("lng"),
#                         "expected_arrival": bus.get("arrival_time"),
#                         "direction": bus.get("direction", ""),
#                         "destination": bus.get("destination", "")
#                     })
                
#                 result = {"bus_positions": bus_positions}
                
#                 # Cache the result for 30 seconds (bus positions change frequently)
#                 if bus_positions:
#                     redis.setex(cache_key, 30, json.dumps(result))
                    
#                 return result if bus_positions else {"message": "Bus not found in live data"}
#             except Exception as e:
#                 logger.warning(f"Error using get_live_bus_positions_async: {e}")
        
#         # Fallback to direct API call if the service method failed
#         api_url = f"{BASE_API_URL}/VehicleMonitoring"
#         params = {
#             "api_key": API_KEY,
#             "agency": agency,
#             "format": "json"  # Prefer JSON if supported
#         }
        
#         logger.info(f"Fetching live bus positions for {agency}:{bus_number} from 511 API")
#         response = requests.get(api_url, params=params, timeout=10)
        
#         if response.status_code != 200:
#             logger.error(f"511 API request failed with status {response.status_code}")
#             raise HTTPException(status_code=response.status_code, detail="511 API request failed")

#         # Check if response is XML or JSON
#         content_type = response.headers.get('Content-Type', '')
#         if 'xml' in content_type.lower():
#             data = xml_to_json(response.text)
#         else:
#             data = response.json()
        
#         # Extract vehicles from Siri response
#         vehicles = data.get("Siri", {}).get("ServiceDelivery", {}).get("VehicleMonitoringDelivery", {})
#         if isinstance(vehicles, list):
#             vehicles = vehicles[0] if vehicles else {}
#         vehicle_activities = vehicles.get("VehicleActivity", [])
        
#         buses = []
#         for vehicle in vehicle_activities:
#             journey = vehicle.get("MonitoredVehicleJourney", {})
#             line_ref = journey.get("LineRef", "")
            
#             # Clean up line_ref (sometimes has format like "SF:38")
#             if isinstance(line_ref, str) and ":" in line_ref:
#                 line_ref = line_ref.split(":")[-1]
                
#             if bus_number in line_ref:
#                 buses.append({
#                     "bus_number": line_ref,
#                     "current_stop": journey.get("MonitoredCall", {}).get("StopPointName", "Unknown"),
#                     "latitude": journey.get("VehicleLocation", {}).get("Latitude"),
#                     "longitude": journey.get("VehicleLocation", {}).get("Longitude"),
#                     "expected_arrival": journey.get("MonitoredCall", {}).get("ExpectedArrivalTime"),
#                     "destination": journey.get("DestinationName", ""),
#                     "direction": journey.get("DirectionRef", "")
#                 })

#         result = {"bus_positions": buses} if buses else {"message": "Bus not found in live data"}
        
#         # Cache result if we found buses
#         if buses:
#             redis.setex(cache_key, 30, json.dumps(result))
            
#         return result
    
#     except HTTPException:
#         raise  # Re-raise HTTP exceptions
#     except Exception as e:
#         logger.exception(f"Error fetching live bus positions: {e}")
        
#         # As a last resort, try to use static GTFS data (just for scheduled stops)
#         try:
#             # This is an approximation using GTFS schedule data
#             # It won't have actual real-time positions
#             trips_for_route = trips_df[trips_df['route_id'] == bus_number]
#             if not trips_for_route.empty:
#                 # Get current time information
#                 now = datetime.now()
#                 current_time = now.time()
#                 current_time_str = now.strftime("%H:%M:%S")
#                 current_day = now.strftime('%A').lower()
                
#                 # Filter to active service for today
#                 service_ids = calendar_df[calendar_df[current_day] == '1']['service_id'].tolist()
#                 active_trips = trips_for_route[trips_for_route['service_id'].isin(service_ids)]
                
#                 if not active_trips.empty:
#                     # Get next scheduled stops for each active trip
#                     scheduled_positions = []
                    
#                     # Get trip IDs that are active today
#                     active_trip_ids = active_trips['trip_id'].tolist()
                    
#                     # Get stop times for these trips
#                     trip_stops = stop_times_df[stop_times_df['trip_id'].isin(active_trip_ids)]
                    
#                     # Find upcoming stops (where departure_time > current_time)
#                     upcoming_stops = trip_stops[trip_stops['departure_time'] > current_time_str]
                    
#                     if not upcoming_stops.empty:
#                         # Sort by departure time to get the next stops
#                         upcoming_stops = upcoming_stops.sort_values('departure_time')
                        
#                         # Get the next few stops for each trip
#                         for trip_id in active_trip_ids[:5]:  # Limit to 5 trips for performance
#                             trip_upcoming = upcoming_stops[upcoming_stops['trip_id'] == trip_id]
#                             if not trip_upcoming.empty:
#                                 next_stop = trip_upcoming.iloc[0]
                                
#                                 # Get stop information
#                                 stop_id = next_stop['stop_id']
#                                 stop_info = stops_df[stops_df['stop_id'] == stop_id]
                                
#                                 if not stop_info.empty:
#                                     stop_name = stop_info.iloc[0]['stop_name']
#                                     stop_lat = float(stop_info.iloc[0]['stop_lat'])
#                                     stop_lon = float(stop_info.iloc[0]['stop_lon'])
                                    
#                                     # Get trip direction and destination
#                                     trip_info = active_trips[active_trips['trip_id'] == trip_id].iloc[0]
#                                     destination = trip_info.get('trip_headsign', 'Unknown')
#                                     direction = trip_info.get('direction_id', '')
                                    
#                                     scheduled_positions.append({
#                                         "bus_number": bus_number,
#                                         "current_stop": stop_name,
#                                         "latitude": stop_lat,
#                                         "longitude": stop_lon,
#                                         "expected_arrival": next_stop['arrival_time'],
#                                         "destination": destination,
#                                         "direction": direction,
#                                         "scheduled": True  # Mark as scheduled, not real-time
#                                     })
                    
#                     if scheduled_positions:
#                         result = {
#                             "message": "No live positions available. Using scheduled data.",
#                             "bus_positions": scheduled_positions,
#                             "scheduled_data": True
#                         }
#                         # Cache these results for a shorter time
#                         redis.setex(cache_key, 120, json.dumps(result))
#                         return result
                    
#                 # If we couldn't find any upcoming scheduled stops
#                 return {"message": "No live or scheduled positions available for this route."}
            
#             # If we get here, we couldn't even find schedule data
#             raise HTTPException(status_code=404, detail="Bus route not found in schedule")
#         except Exception as nested_e:
#             logger.exception(f"Failed to get fallback GTFS data: {nested_e}")
#             raise HTTPException(status_code=500, detail="Failed to fetch live or scheduled data")

# @router.get("/cached-bus-positions")
# def get_cached_bus_positions(bus_number: str, agency: str):
#     """
#     Get cached bus position data with fallback to live data.
#     Uses Redis cache with 5 minute expiration.
#     """
#     cache_key = f"bus:positions:{agency}:{bus_number}"
#     cached_data = redis.get(cache_key)

#     if cached_data:
#         try:
#             logger.info(f"Cache hit for {cache_key}")
#             return json.loads(cached_data)
#         except json.JSONDecodeError:
#             logger.warning(f"Invalid cached JSON for {cache_key}")
    
#     # Cache miss - need to get live data
#     logger.info(f"Cache miss for {cache_key} - fetching live data")
    
#     try:
#         # Run the async method synchronously
#         import asyncio
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
        
#         try:
#             buses = loop.run_until_complete(
#                 bus_service.get_live_bus_positions_async(agency, bus_number)
#             )
#             loop.close()
            
#             # Format the data to match our expected output
#             bus_positions = []
#             for bus in buses:
#                 bus_positions.append({
#                     "bus_number": bus.get("route", ""),
#                     "current_stop": bus.get("next_stop", {}).get("name", "Unknown"),
#                     "latitude": bus.get("lat"),
#                     "longitude": bus.get("lng"),
#                     "expected_arrival": bus.get("arrival_time", ""),
#                     "direction": bus.get("direction", ""),
#                     "destination": bus.get("destination", "")
#                 })
            
#             result = {"bus_positions": bus_positions}
            
#             # Cache the result (5 min TTL)
#             if bus_positions:
#                 redis.setex(cache_key, 300, json.dumps(result))
#                 logger.info(f"Cached {len(bus_positions)} bus positions for {cache_key}")
#             else:
#                 logger.info(f"No buses found for {bus_number}")
#                 # Cache negative result for a shorter time to reduce load but not impact UX too much
#                 redis.setex(cache_key, 60, json.dumps({"message": "No buses found"}))
                
#             return result if bus_positions else {"message": "No buses found"}
            
#         except Exception as inner_e:
#             logger.error(f"Error running async bus position method: {inner_e}")
#             loop.close()
#             raise
            
#     except Exception as e:
#         logger.exception(f"Error in get_cached_bus_positions for {bus_number}: {e}")
#         raise HTTPException(
#             status_code=500, 
#             detail=f"Failed to fetch bus positions: {str(e)}"
#         )
