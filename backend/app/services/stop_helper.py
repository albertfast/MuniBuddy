from typing import List, Dict, Any
from datetime import datetime
from colorama import Fore, Style
import pandas as pd
import math

from app.services.debug_logger import log_debug


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
    except (ValueError, TypeError) as e:
        log_debug(f"[WARN] Error in calculate_distance: {e}")
        return float('inf')

def load_stops(gtfs_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        stops = []
        for agency in ["muni", "bart"]:
            if agency in gtfs_data and 'stops' in gtfs_data[agency]:
                agency_stops = gtfs_data[agency]['stops']

                # ✅ Güvenli kontrol
                if isinstance(agency_stops, pd.DataFrame) and not agency_stops.empty:
                    for _, row in agency_stops.iterrows():
                        stops.append({
                            'stop_id': row['stop_id'],
                            'stop_name': row['stop_name'],
                            'stop_lat': float(row['stop_lat']),
                            'stop_lon': float(row['stop_lon']),
                            'agency': agency
                        })

        if not stops:
            log_debug("✗ No stops data in GTFS")
            return []

        log_debug(f"✓ Loaded {len(stops)} stops from GTFS data")
        return stops

    except Exception as e:
        log_debug(f"✗ Error loading stops: {str(e)}")
        return []

async def find_nearby_stops(
    lat: float,
    lon: float,
    gtfs_data: Dict[str, pd.DataFrame],
    stops: List[Dict[str, Any]],
    radius_miles: float = 0.15,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Find nearby transit stops and enrich them with route information.
    """
    nearby_stops = []

    for stop in stops:
        distance = calculate_distance(lat, lon, stop['stop_lat'], stop['stop_lon'])
        if distance > radius_miles:
            continue

        original_stop_id = stop['stop_id']
        gtfs_stop_id = f"1{original_stop_id}" if stop['agency'] == 'muni' and not original_stop_id.startswith('1') else original_stop_id

        try:
            stop_times_df = gtfs_data.get('stop_times', pd.DataFrame())
            trips_df = gtfs_data.get('trips', pd.DataFrame())
            routes_df = gtfs_data.get('routes', pd.DataFrame())

            if stop_times_df.empty:
                log_debug(f"⚠️ stop_times_df is empty for stop: {gtfs_stop_id}")
                continue
            if trips_df.empty:
                log_debug(f"⚠️ trips_df is empty for stop: {gtfs_stop_id}")
                continue
            if routes_df.empty:
                log_debug(f"⚠️ routes_df is empty for stop: {gtfs_stop_id}")
                continue

            stop_times = stop_times_df[stop_times_df['stop_id'] == gtfs_stop_id]
            if stop_times.empty:
                log_debug(f"⚠️ No stop_times match found for stop_id: {gtfs_stop_id}")
                continue

            trips = trips_df[trips_df['trip_id'].isin(stop_times['trip_id'])]
            if trips.empty:
                log_debug(f"⚠️ No trips found for stop_id: {gtfs_stop_id}")
                continue

            routes = routes_df[routes_df['route_id'].isin(trips['route_id'])].drop_duplicates()
            if routes.empty:
                log_debug(f"⚠️ No routes found for stop_id: {gtfs_stop_id}")
                continue

            route_info = []
            for _, route in routes.iterrows():
                destination = route['route_long_name'].split(' - ')[-1] if ' - ' in route['route_long_name'] else route['route_long_name']
                route_info.append({
                    'route_id': route['route_id'],
                    'route_number': route['route_short_name'],
                    'destination': destination
                })

            stop_info = stop.copy()
            stop_info['distance_miles'] = round(distance, 2)
            stop_info['routes'] = route_info
            stop_info['id'] = original_stop_id
            stop_info['gtfs_stop_id'] = gtfs_stop_id

            nearby_stops.append(stop_info)

        except Exception as e:
            log_debug(f"✗ Error while processing stop {original_stop_id}: {e}")
            continue

    log_debug(f"✓ Found {len(nearby_stops)} nearby stops within {radius_miles} miles")
    nearby_stops.sort(key=lambda x: x['distance_miles'])
    return nearby_stops[:limit]