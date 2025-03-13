import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")
AGENCY_IDS = os.getenv("AGENCY_ID", "SF").split(',')

def fetch_real_time_bus_data():
    """Fetch real-time bus data from 511 API."""
    results = []
    for agency in AGENCY_IDS:
        url = f"http://api.511.org/transit/StopMonitoring?api_key={API_KEY}&agency={agency}"
        response = requests.get(url)
        if response.status_code == 200:
            results.append(response.json())
    return results


# import requests
# import json
# import pandas as pd
# import os
# from fastapi import HTTPException
# import xml.etree.ElementTree as ET
# from app.config import API_KEY, GTFS_DIR, AGENCY_ID

# gtfs_data = {}

# def load_gtfs_data_into_memory():
#     """Loads GTFS data into the global 'gtfs_data' dictionary."""
#     global gtfs_data
#     routes_file = os.path.join(GTFS_DIR, "routes.txt")
#     trips_file = os.path.join(GTFS_DIR, "trips.txt")
#     #stops_file = os.path.join(GTFS_DIR, "stops.txt")  # Add if you need stop details

#     try:
#         gtfs_data['routes'] = pd.read_csv(routes_file, dtype=str)
#         gtfs_data['trips'] = pd.read_csv(trips_file, dtype=str)
#         #gtfs_data['stops'] = pd.read_csv(stops_file, dtype=str) # Add if needed
#         print("GTFS data loaded successfully.")
#     except FileNotFoundError as e:
#         print(f"Error loading GTFS data: {e}.  Make sure GTFS files are in {GTFS_DIR}")
#         #  You might want to exit the application here, or raise an exception.
#     except pd.errors.ParserError as e:
#         print(f"Error parsing GTFS data: {e}")
#         #  Handle parsing errors.


# async def fetch_live_bus_positions(route_short_name: str, agency: str):
#     """Fetches live bus positions from the 511 API using VehiclePositions."""
#     api_url = f"http://api.511.org/transit/vehiclepositions?api_key={API_KEY}&agency={agency}&routeCode={route_short_name}"
#     #print(api_url)
#     response = requests.get(api_url)
#     response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

#     try:
#         return response.json()
#     except json.JSONDecodeError:
#         raise HTTPException(status_code=500, detail="Error parsing JSON response from 511 API")


# async def get_live_bus_positions(route_short_name: str, agency: str):
#     """Gets live bus positions and enhances with GTFS data."""
#     live_data = await fetch_live_bus_positions(route_short_name, agency)

#     # Check for valid response structure
#     if not isinstance(live_data, dict) or 'vehicle' not in live_data.get('Siri', {}).get('ServiceDelivery', {}).get('VehicleMonitoringDelivery', [{}])[0]:
#         raise HTTPException(status_code=500, detail="Unexpected response format from 511 API")
    
#     vehicle_activity = live_data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery'][0]['VehicleActivity']
#     bus_positions = []

#     # Load GTFS data (if not already loaded).  In a real app, load this once at startup.
#     if 'routes' not in gtfs_data or 'trips' not in gtfs_data:
#         load_gtfs_data_into_memory()

#     for vehicle in vehicle_activity:
#         journey = vehicle.get('MonitoredVehicleJourney', {})
#         line_ref = journey.get('LineRef')
#         vehicle_ref = journey.get('VehicleRef') # Get the vehicle identifier
        
#         # Basic validation
#         if not line_ref or not journey.get('VehicleLocation'):
#             continue  # Skip this vehicle if essential data is missing

#         # --- GTFS Enhancement ---
#         route_name = "Unknown"
#         if 'routes' in gtfs_data:
#             matching_route = gtfs_data['routes'][gtfs_data['routes']['route_id'] == line_ref]
#             if not matching_route.empty:
#                 route_name = matching_route.iloc[0].get('route_long_name', "Unknown")

#         # Extract and format data
#         bus_positions.append({
#             "bus_number": line_ref,
#             "vehicle_ref": vehicle_ref, # Include the vehicle ID
#             "route_name": route_name,
#             "latitude": float(journey['VehicleLocation']['Latitude']),  # Ensure float
#             "longitude": float(journey['VehicleLocation']['Longitude']), # Ensure float
#             "bearing": journey.get('Bearing'), # Optional: Include bearing if available
#             "current_stop": journey.get("MonitoredCall",{}).get("StopPointName"), #Optional: Get current stop
#             "arrival_time": journey.get("MonitoredCall",{}).get("ExpectedArrivalTime") #Optional: Get arrival time
#         })
#     return bus_positions
    

# def get_all_gtfs_routes():
#     """Retrieves all routes from the in-memory GTFS data."""
#     if 'routes' not in gtfs_data:
#         raise HTTPException(status_code=404, detail="GTFS routes data not loaded.")
#     return gtfs_data['routes'].to_dict(orient="records")

# def get_gtfs_route_details(route_short_name: str):
#     """Retrieves route details from the in-memory GTFS data."""
#     if 'routes' not in gtfs_data:
#          raise HTTPException(status_code=404, detail="GTFS routes data not loaded.")

#     routes_df = gtfs_data['routes']
#     route_info = routes_df[routes_df["route_short_name"] == route_short_name]

#     if route_info.empty:
#       raise HTTPException(status_code=404, detail="Route not found")

#     route_details = route_info.to_dict(orient="records")[0]
#     return route_details

# """
# def fetch_bus_positions(agency: str):
    
#     # Fetch real-time bus positions from the 511 API.
    
#     api_url = f"http://api.511.org/transit/StopMonitoring?api_key={API_KEY}&agency={agency}&format=xml"
#     response = requests.get(api_url)

#     if response.status_code != 200:
#         raise Exception(f"Error fetching bus data from API: {response.status_code}")

#     return response.text  # Return XML data


# def parse_bus_data(xml_text):
 
#    # Parses XML response and converts it to a structured JSON format.
  
#     namespaces = {'siri': 'http://www.siri.org.uk/siri'}
#     root = ET.fromstring(xml_text)
    
#     bus_positions = []
#     for monitored in root.findall(".//siri:MonitoredVehicleJourney", namespaces):
#         try:
#             bus_data = {
#                 "bus_number": monitored.find("siri:LineRef", namespaces).text or "Unknown",
#                 "published_name": monitored.find("siri:PublishedLineName", namespaces).text or "Unknown",
#                 "current_stop": monitored.find("siri:MonitoredCall/siri:StopPointName", namespaces).text or "Unknown",
#                 "latitude": monitored.find("siri:VehicleLocation/siri:Latitude", namespaces).text or "0",
#                 "longitude": monitored.find("siri:VehicleLocation/siri:Longitude", namespaces).text or "0",
#                 "arrival_time": monitored.find("siri:MonitoredCall/siri:ExpectedArrivalTime", namespaces).text or "N/A",
#                 "destination": monitored.find("siri:DestinationName", namespaces).text or "Unknown"
#             }
#             bus_positions.append(bus_data)
#         except AttributeError:
#             continue  # Skip entries with missing data

#     return bus_positions
# """