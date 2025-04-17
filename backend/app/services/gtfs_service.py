import os
import pandas as pd
from typing import Dict

def load_gtfs_data(gtfs_path: str) -> Dict[str, pd.DataFrame]:
    """
    Load all standard GTFS files from the specified directory into a dictionary of pandas DataFrames.
    Supports routes, trips, stops, stop_times, calendar, calendar_dates, fare_attributes, fare_rules,
    shapes, frequencies, transfers, pathways, levels, translations, feed_info.
    
    Returns:
        dict: A dictionary where each key is a GTFS file name (without .txt) and the value is a DataFrame.
    """
    gtfs_files = [
        "agency", "calendar", "calendar_dates", "fare_attributes", "fare_rules",
        "feed_info", "frequencies", "levels", "pathways", "routes",
        "shapes", "stop_times", "stops", "transfers", "translations", "trips"
    ]

    gtfs_data: Dict[str, pd.DataFrame] = {}

    for file in gtfs_files:
        file_path = os.path.join(gtfs_path, f"{file}.txt")
        if os.path.exists(file_path):
            try:
                gtfs_data[file] = pd.read_csv(file_path, dtype=str)
                print(f"[✓] Loaded {file}.txt ({len(gtfs_data[file])} rows)")
            except Exception as e:
                print(f"[ERROR] Failed to load {file}.txt: {e}")
                gtfs_data[file] = pd.DataFrame()
        else:
            print(f"[WARNING] Missing {file}.txt — continuing with empty DataFrame")
            gtfs_data[file] = pd.DataFrame()

    print(f"[DEBUG] GTFS summary from {gtfs_path} → {len(gtfs_data['stops'])} stops, {len(gtfs_data['stop_times'])} stop_times, {len(gtfs_data['trips'])} trips")
    return gtfs_data
