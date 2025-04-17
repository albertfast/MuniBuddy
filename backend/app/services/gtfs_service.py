import os
import pandas as pd
from typing import Dict

GTFS_FILE_LIST = [
    "agency", "attributions", "calendar", "calendar_attributes", "calendar_dates",
    "directions", "fare_attributes", "fare_rider_categories", "fare_rules", "farezone_attributes",
    "feed_info", "levels", "pathways", "route_attributes", "routes", "rider_categories",
    "shapes", "stop_times", "stops", "timepoints", "transfers", "translations", "trips"
]

def load_gtfs_data(gtfs_path: str) -> Dict[str, pd.DataFrame]:
    """
    Load all known GTFS files into a dictionary of DataFrames.
    If a file is missing, an empty DataFrame is used instead.

    Args:
        gtfs_path (str): Path to the GTFS directory

    Returns:
        Dict[str, pd.DataFrame]: Mapping of file keys to DataFrames
    """
    gtfs_data: Dict[str, pd.DataFrame] = {}

    print(f"[GTFS LOADER] Loading files from: {gtfs_path}")
    for file_name in GTFS_FILE_LIST:
        file_path = os.path.join(gtfs_path, f"{file_name}.txt")
        try:
            if os.path.exists(file_path):
                df = pd.read_csv(file_path, dtype=str)
                gtfs_data[file_name] = df
                print(f"[✓] Loaded {file_name}.txt → {len(df)} rows")
            else:
                print(f"[!] {file_name}.txt not found. Using empty DataFrame.")
                gtfs_data[file_name] = pd.DataFrame()
        except Exception as e:
            print(f"[ERROR] Failed to read {file_name}.txt → {e}")
            gtfs_data[file_name] = pd.DataFrame()

    # Summary
    print(f"[SUMMARY] {len(gtfs_data['stops'])} stops, {len(gtfs_data['stop_times'])} stop_times, {len(gtfs_data['trips'])} trips")
    return gtfs_data
