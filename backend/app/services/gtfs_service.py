import pandas as pd
import os

def load_gtfs_data():
    """Loads GTFS data into pandas DataFrames"""
    try:
        # GTFS paths (relative to backend folder)
        bart_path = "gtfs_data/bart_gtfs-current"
        muni_path = "gtfs_data/muni_gtfs-current"
        
        # Load BART data
        bart_routes_df = pd.read_csv(os.path.join(bart_path, "routes.txt"), dtype={'route_id': str, 'route_short_name': str})
        if 'route_short_name' not in bart_routes_df.columns:
            bart_routes_df['route_short_name'] = bart_routes_df['route_id']
        bart_trips_df = pd.read_csv(os.path.join(bart_path, "trips.txt"), dtype=str)
        bart_stops_df = pd.read_csv(os.path.join(bart_path, "stops.txt"), dtype=str)
        
        # Load Muni data
        muni_routes_df = pd.read_csv(os.path.join(muni_path, "routes.txt"), dtype={'route_id': str, 'route_short_name': str})
        muni_trips_df = pd.read_csv(os.path.join(muni_path, "trips.txt"), dtype=str)
        muni_stops_df = pd.read_csv(os.path.join(muni_path, "stops.txt"), dtype=str)
        muni_stop_times_df = pd.read_csv(os.path.join(muni_path, "stop_times.txt"), dtype=str)
        
        # Load calendar data as integers
        muni_calendar_df = pd.read_csv(os.path.join(muni_path, "calendar.txt"), 
                                     dtype={
                                         'service_id': str,
                                         'monday': int,
                                         'tuesday': int,
                                         'wednesday': int,
                                         'thursday': int,
                                         'friday': int,
                                         'saturday': int,
                                         'sunday': int,
                                         'start_date': int,
                                         'end_date': int
                                     })
        
        # Normalize stop names for matching
        bart_stops_df["stop_id"] = bart_stops_df["stop_id"].str.replace("place_", "")
        muni_stops_df["stop_id"] = muni_stops_df["stop_id"].str.replace("place_", "")
        
        # Add agency information
        bart_routes_df['agency_id'] = 'BA'
        muni_routes_df['agency_id'] = 'SFMTA'
        
        # Combine all data
        routes_df = pd.concat([bart_routes_df, muni_routes_df], ignore_index=True)
        trips_df = pd.concat([bart_trips_df, muni_trips_df], ignore_index=True)
        stops_df = pd.concat([bart_stops_df, muni_stops_df], ignore_index=True)
        
        return routes_df, trips_df, stops_df, muni_stop_times_df, muni_calendar_df
    except Exception as e:
        raise Exception(f"Error loading GTFS data: {str(e)}")
