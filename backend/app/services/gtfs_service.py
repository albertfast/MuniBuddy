import pandas as pd
import os
from app.config import settings

def load_gtfs_data():
    muni_path =  os.getenv("BART_GTFS_PATH", "./gtfs_data/bart_gtfs-current")
    bart_path = os.getenv("BART_GTFS_PATH", "./gtfs_data/bart_gtfs-current")

    try:
        # Skip BART if file doesn't exist (for local testing)
        if not os.path.exists(os.path.join(bart_path, "routes.txt")):
            print("[INFO] Skipping BART GTFS data (file not found)")
            bart_routes_df = pd.DataFrame()
        else:
            bart_routes_df = pd.read_csv(os.path.join(bart_path, "routes.txt"), dtype={'route_id': str, 'route_short_name': str})
        
        muni_routes_df = pd.read_csv(os.path.join(muni_path, "routes.txt"), dtype={'route_id': str, 'route_short_name': str})
        trips_df = pd.read_csv(os.path.join(muni_path, "trips.txt"), dtype=str)
        stops_df = pd.read_csv(os.path.join(muni_path, "stops.txt"), dtype=str)
        stop_times_df = pd.read_csv(os.path.join(muni_path, "stop_times.txt"), dtype=str)
        calendar_df = pd.read_csv(os.path.join(muni_path, "calendar.txt"), dtype=str)

        # Combine both if needed
        combined_routes_df = pd.concat([bart_routes_df, muni_routes_df], ignore_index=True)

        return combined_routes_df, trips_df, stops_df, stop_times_df, calendar_df

    except Exception as e:
        raise Exception(f"Error loading GTFS data: {str(e)}")
