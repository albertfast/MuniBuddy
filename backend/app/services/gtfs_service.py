import pandas as pd

def load_gtfs_data():
    """Loads GTFS data into pandas DataFrames"""
    try:
        routes_df = pd.read_csv("gtfs_data/routes.txt", dtype={'route_id': str, 'route_short_name': str})
        if 'route_short_name' not in routes_df.columns:
            routes_df['route_short_name'] = routes_df['route_id']
        trips_df = pd.read_csv("gtfs_data/trips.txt", dtype=str)
        stops_df = pd.read_csv("gtfs_data/stops.txt", dtype=str)
        
        # Normalize stop names for matching
        stops_df["stop_id"] = stops_df["stop_id"].str.replace("place_", "")
        
        return routes_df, trips_df, stops_df
    except Exception as e:
        raise Exception(f"Error loading GTFS data: {str(e)}")
