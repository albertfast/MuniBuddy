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

async def load_stops(gtfs_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Load all stops from GTFS data.

    Args:
        gtfs_data (Dict[str, Any]): GTFS data dictionary.

    Returns:
        List[Dict[str, Any]]: List of stops with their coordinates
    """
    try:
        stops = []
        for agency in ["muni", "bart"]:
            if agency in gtfs_data and 'stops' in gtfs_data[agency]:
                agency_stops = gtfs_data[agency]['stops']
                if not agency_stops.empty:
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

def find_nearby_stops(lat: float, lon: float, gtfs_data: Dict[str, Any], radius_miles: float = 0.15, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Find nearby transit stops within a radius and attach route info.
    """
    stops = []

    for agency in ['muni', 'bart']:
        if agency not in gtfs_data or 'stops' not in gtfs_data[agency]:
            continue

        stops_df = gtfs_data[agency]['stops']
        if stops_df.empty:
            continue

        for _, row in stops_df.iterrows():
            distance = calculate_distance(lat, lon, row['stop_lat'], row['stop_lon'])
            if distance > radius_miles:
                continue

            stop_id = row['stop_id']
            gtfs_stop_id = f"1{stop_id}" if agency == 'muni' and not stop_id.startswith('1') else stop_id

            try:
                stop_times_df = gtfs_data[agency].get('stop_times', pd.DataFrame())
                if stop_times_df.empty:
                    continue
                stop_times = stop_times_df[stop_times_df['stop_id'] == gtfs_stop_id]
                if stop_times.empty:
                    log_debug(f"⚠️ No stop_times for {gtfs_stop_id}")
                    continue

                weekday = datetime.now().strftime("%A").lower()
                calendar_df = gtfs_data[agency].get('calendar', pd.DataFrame())
                if calendar_df.empty:
                    continue

                active_services = calendar_df[
                    (calendar_df[weekday] == 1) &
                    (pd.to_numeric(calendar_df['start_date']) <= int(datetime.now().strftime("%Y%m%d"))) &
                    (pd.to_numeric(calendar_df['end_date']) >= int(datetime.now().strftime("%Y%m%d")))
                ]['service_id']

                trips_df = gtfs_data[agency].get('trips', pd.DataFrame())
                if trips_df.empty:
                    continue

                active_trips = trips_df[trips_df['service_id'].isin(active_services)]
                valid_trips = stop_times.merge(
                    active_trips[['trip_id', 'route_id', 'direction_id']],
                    on='trip_id'
                )

                routes_df = gtfs_data[agency].get('routes', pd.DataFrame())
                if routes_df.empty:
                    continue

                routes = routes_df[routes_df['route_id'].isin(valid_trips['route_id'])].drop_duplicates()

                route_info = []
                for _, route in routes.iterrows():
                    destination = route['route_long_name'].split(' - ')[-1] if ' - ' in route['route_long_name'] else route['route_long_name']
                    route_info.append({
                        'route_id': route['route_id'],
                        'route_number': route['route_short_name'],
                        'destination': destination
                    })

                log_debug(f"✓ Found {len(route_info)} routes for stop {gtfs_stop_id}")

                stops.append({
                    'stop_id': stop_id,
                    'gtfs_stop_id': gtfs_stop_id,
                    'stop_name': row['stop_name'],
                    'stop_lat': row['stop_lat'],
                    'stop_lon': row['stop_lon'],
                    'agency': agency,
                    'distance_miles': round(distance, 2),
                    'routes': route_info,
                    'id': stop_id
                })

            except Exception as e:
                log_debug(f"✗ Error for stop {stop_id} ({agency}): {e}")
                continue

    stops.sort(key=lambda x: x['distance_miles'])
    return stops[:limit]