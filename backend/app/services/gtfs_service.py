import os
import pandas as pd

def load_gtfs_data(muni_path: str):
    try:
        routes_df = pd.read_csv(os.path.join(muni_path, "routes.txt"), dtype=str)
        trips_df = pd.read_csv(os.path.join(muni_path, "trips.txt"), dtype=str)
        stops_df = pd.read_csv(os.path.join(muni_path, "stops.txt"), dtype=str)
        stop_times_df = pd.read_csv(os.path.join(muni_path, "stop_times.txt"), dtype=str)
        calendar_df = pd.read_csv(os.path.join(muni_path, "calendar.txt"), dtype=str)

        print(f"[DEBUG] Loaded {len(stops_df)} stops")
        print(f"[DEBUG] Loaded {len(stop_times_df)} stop times")
        print(f"[DEBUG] Loaded {len(trips_df)} trips")
        print(f"[DEBUG] Loaded {len(routes_df)} routes")
        print(f"[DEBUG] Loaded {len(calendar_df)} calendar entries")

        return routes_df, trips_df, stops_df, stop_times_df, calendar_df

    except Exception as e:
        raise Exception(f"Error loading GTFS data: {str(e)}")
