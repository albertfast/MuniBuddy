from typing import List, Dict, Any
from datetime import datetime
import pandas as pd
import math
from app.services.debug_logger import log_debug
from app.config import settings


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.
    Returns distance in miles.
    """
    if None in [lat1, lon1, lat2, lon2]:
        log_debug(f"Invalid coordinates: ({lat1}, {lon1}) -> ({lat2}, {lon2})")
        return float('inf')
    try:
        R = 3959  # Earth's radius in miles
        lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c
    except Exception as e:
        log_debug(f"[WARN] Error in calculate_distance: {e}")
        return float('inf')


def load_stops(agency: str) -> List[Dict[str, Any]]:
    try:
        stops = []
        gtfs_tuple = settings.get_gtfs_data(agency)
        if not gtfs_tuple:
            log_debug(f"⚠️ GTFS data not loaded for agency: {agency}")
            return []

        _, _, stops_df, *_ = gtfs_tuple

        if isinstance(stops_df, pd.DataFrame) and not stops_df.empty:
            for _, row in stops_df.iterrows():
                stop = {
                    'stop_id': row['stop_id'],
                    'stop_name': row['stop_name'],
                    'stop_lat': float(row['stop_lat']),
                    'stop_lon': float(row['stop_lon']),
                    'agency': agency
                }
                if 'stop_code' in row and pd.notna(row['stop_code']):
                    stop['stop_code'] = str(row['stop_code'])
                stops.append(stop)

        if not stops:
            log_debug(f"✗ No stops loaded for agency: {agency}")
            return []

        log_debug(f"✓ Loaded {len(stops)} stops for agency: {agency}")
        return stops

    except Exception as e:
        log_debug(f"✗ Error loading stops for {agency}: {str(e)}")
        return []


def find_nearby_stops(
    lat: float,
    lon: float,
    stops: List[Dict[str, Any]],
    radius_miles: float = 0.15,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Find nearby transit stops based on geographic distance only.
    """
    nearby_stops = []
    for stop in stops:
        distance = calculate_distance(lat, lon, stop["stop_lat"], stop["stop_lon"])
        if distance <= radius_miles:
            stop_info = stop.copy()
            stop_info["distance_miles"] = round(distance, 2)
            nearby_stops.append(stop_info)

    nearby_stops.sort(key=lambda x: x["distance_miles"])
    log_debug(f"✓ Found {len(nearby_stops)} nearby stops within {radius_miles} miles (no stop_times filtering)")
    return nearby_stops[:limit]


def get_nearby_stops(lat: float, lon: float, radius: float = 0.15, agency: str = "muni", limit: int = 5) -> List[Dict[str, Any]]:
    """
    Unified nearby stop discovery logic used by all services.
    """
    log_debug(f"[Unified] Fetching nearby stops for agency={agency} at location=({lat}, {lon})")
    stops = load_stops(agency)
    if not stops:
        return []

    return find_nearby_stops(lat, lon, stops, radius, limit)
