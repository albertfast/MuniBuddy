import os
import requests
import pandas as pd
from geopy.geocoders import Nominatim
from scipy.spatial import KDTree

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Define API Key and GTFS data directory
API_KEY = os.getenv("API_KEY")
GTFS_DIR = os.path.join(os.path.dirname(__file__), "gtfs_data")

# Convert user addresses to coordinates
geolocator = Nominatim(user_agent="muni_app")

try:
    start_location = geolocator.geocode("432 Geary St, San Francisco")
    end_location = geolocator.geocode("115 33th Ave, San Francisco")
    
    if not start_location or not end_location:
        print("Location information could not be retrieved.")
        exit()

    start_coords = (start_location.latitude, start_location.longitude)
    end_coords = (end_location.latitude, end_location.longitude)

    # Read GTFS stop data
    stops_path = os.path.join(GTFS_DIR, "stops.txt")
    stop_times_path = os.path.join(GTFS_DIR, "stop_times.txt")
    trips_path = os.path.join(GTFS_DIR, "trips.txt")

    stops = pd.read_csv(stops_path)
    stops["stop_lat_lon"] = list(zip(stops["stop_lat"], stops["stop_lon"]))

    # Find nearest stops
    stop_tree = KDTree(stops["stop_lat_lon"].tolist())
    _, start_index = stop_tree.query(start_coords)
    _, end_index = stop_tree.query(end_coords)

    start_stop_id = stops.iloc[start_index]["stop_id"]
    end_stop_id = stops.iloc[end_index]["stop_id"]

    # Find routes passing through these stops
    stop_times = pd.read_csv(stop_times_path)
    trips = pd.read_csv(trips_path)

    start_routes = stop_times[stop_times["stop_id"] == start_stop_id]["trip_id"].unique()
    end_routes = stop_times[stop_times["stop_id"] == end_stop_id]["trip_id"].unique()

    common_routes = set(start_routes) & set(end_routes)

    # Show suitable routes to the user
    if common_routes:
        matching_routes = trips[trips["trip_id"].isin(common_routes)]["route_id"].unique()
        print("These routes match your itinerary:", matching_routes)
    else:
        print("No direct routes found between these two points.")

except requests.exceptions.RequestException as e:
    print(f"Network error: {e}")