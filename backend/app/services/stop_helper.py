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

async def find_nearby_stops(
    lat: float,
    lon: float,
    gtfs_data: Dict[str, pd.DataFrame],
    stops: List[Dict[str, Any]],
    radius_miles: float = 0.1,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Find nearby transit stops and enrich with route info.
    """
    nearby_stops = []

    for stop in stops:
        distance = calculate_distance(lat, lon, stop['stop_lat'], stop['stop_lon'])

        if distance <= radius_miles:
            original_stop_id = stop['stop_id']
            api_stop_id = original_stop_id[1:] if original_stop_id.startswith('1') else original_stop_id

            try:
                stop_times_df = gtfs_data.get('stop_times', pd.DataFrame())
                trips_df = gtfs_data.get('trips', pd.DataFrame())
                routes_df = gtfs_data.get('routes', pd.DataFrame())

                if stop_times_df.empty or trips_df.empty or routes_df.empty:
                    log_debug(f"✗ One or more GTFS components missing for stop {original_stop_id}")
                    continue

                stop_times = stop_times_df[stop_times_df['stop_id'] == original_stop_id]
                if stop_times.empty:
                    log_debug(f"⚠️ No stop_times for stop {original_stop_id}")
                    continue

                trips = trips_df[trips_df['trip_id'].isin(stop_times['trip_id'])]
                routes = routes_df[routes_df['route_id'].isin(trips['route_id'])].drop_duplicates()

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
                stop_info['id'] = api_stop_id
                stop_info['stop_id'] = api_stop_id
                stop_info['gtfs_stop_id'] = original_stop_id

                nearby_stops.append(stop_info)

            except KeyError as e:
                log_debug(f"✗ KeyError while processing stop {original_stop_id}: {e}")
                continue
            except Exception as e:
                log_debug(f"✗ Error while processing stop {original_stop_id}: {e}")
                continue

    nearby_stops.sort(key=lambda x: x['distance_miles'])
    return nearby_stops[:limit]
