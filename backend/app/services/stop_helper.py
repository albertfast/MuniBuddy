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
                stops.append({
                    'stop_id': row['stop_id'],
                    'stop_name': row['stop_name'],
                    'stop_lat': float(row['stop_lat']),
                    'stop_lon': float(row['stop_lon']),
                    'agency': agency
                })

        if not stops:
            log_debug(f"✗ No stops loaded for agency: {agency}")
            return []

        log_debug(f"✓ Loaded {len(stops)} stops for agency: {agency}")
        return stops

    except Exception as e:
        log_debug(f"✗ Error loading stops for {agency}: {str(e)}")
        return []

    except Exception as e:
        log_debug(f"✗ Error in load_stops: {str(e)}")
        return []

def find_nearby_stops(
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
        distance = calculate_distance(lat, lon, stop["stop_lat"], stop["stop_lon"])
        if distance > radius_miles:
            continue

        agency = stop["agency"]
        original_stop_id = stop["stop_id"]
        gtfs_stop_id = f"1{original_stop_id}" if agency == "muni" and not original_stop_id.startswith("1") else original_stop_id

        try:
            gtfs_data = settings.get_gtfs_data(agency)
            if not gtfs_data or len(gtfs_data) < 5:
                log_debug(f"✗ GTFS data missing or incomplete for agency {agency}")
                continue

            routes_df, trips_df, _, stop_times_df, calendar_df = gtfs_data

            if any(df.empty for df in [routes_df, trips_df, stop_times_df, calendar_df]):
                log_debug(f"✗ One or more GTFS dataframes empty for stop {gtfs_stop_id}")
                continue

            stop_times = stop_times_df[stop_times_df["stop_id"] == gtfs_stop_id]
            if stop_times.empty:
                log_debug(f"⚠️ No stop_times found for stop_id {gtfs_stop_id}")
                continue

            weekday = datetime.now().strftime("%A").lower()
            calendar_active = calendar_df[
                (calendar_df[weekday] == "1") &
                (calendar_df["start_date"] <= datetime.now().strftime("%Y%m%d")) &
                (calendar_df["end_date"] >= datetime.now().strftime("%Y%m%d"))
            ]

            active_service_ids = calendar_active["service_id"]
            active_trips = trips_df[trips_df["service_id"].isin(active_service_ids)]
            if active_trips.empty:
                log_debug(f"⚠️ No active trips found for stop_id {gtfs_stop_id}")
                continue

            valid_trips = stop_times.merge(active_trips, on="trip_id")
            valid_routes = routes_df[routes_df["route_id"].isin(valid_trips["route_id"])].drop_duplicates()
            if valid_routes.empty:
                log_debug(f"⚠️ No routes found for stop_id {gtfs_stop_id}")
                continue

            route_info = []
            for _, route in valid_routes.iterrows():
                destination = route["route_long_name"].split(" - ")[-1] if " - " in route["route_long_name"] else route["route_long_name"]
                route_info.append({
                    "route_id": route["route_id"],
                    "route_number": route["route_short_name"],
                    "destination": destination
                })

            stop_info = stop.copy()
            stop_info["distance_miles"] = round(distance, 2)
            stop_info["routes"] = route_info
            stop_info["stop_id"] = original_stop_id[1:] if original_stop_id.startswith("1") else original_stop_id
            stop_info["gtfs_stop_id"] = gtfs_stop_id

            nearby_stops.append(stop_info)

        except Exception as e:
            log_debug(f"✗ Exception while processing stop {original_stop_id} ({agency}): {e}")
            continue

    nearby_stops.sort(key=lambda x: x["distance_miles"])
    log_debug(f"✓ Found {len(nearby_stops)} nearby stops within {radius_miles} miles")
    return nearby_stops[:limit]