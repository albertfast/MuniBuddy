import os
import pandas as pd

def load_gtfs_data(gtfs_path: str):
    try:
        routes_df = pd.read_csv(os.path.join(gtfs_path, "routes.txt"), dtype=str)
        trips_df = pd.read_csv(os.path.join(gtfs_path, "trips.txt"), dtype=str)
        stops_df = pd.read_csv(os.path.join(gtfs_path, "stops.txt"), dtype=str)
        stop_times_df = pd.read_csv(os.path.join(gtfs_path, "stop_times.txt"), dtype=str)
        calendar_df = pd.read_csv(os.path.join(gtfs_path, "calendar.txt"), dtype=str)

        print(f"[DEBUG] {gtfs_path}: {len(stops_df)} stops, {len(stop_times_df)} stop_times, {len(trips_df)} trips")
        return routes_df, trips_df, stops_df, stop_times_df, calendar_df

    except Exception as e:
        raise Exception(f"Error loading GTFS data from {gtfs_path}: {str(e)}")
