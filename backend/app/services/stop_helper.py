from typing import List, Dict, Any
from datetime import datetime
import pandas as pd
import math

from app.services.debug_logger import log_debug
from app.services.gtfs_service import GTFSService
from app.config import settings  

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using Haversine formula (miles)."""
    if None in [lat1, lon1, lat2, lon2]:
        log_debug(f"Invalid coordinates: ({lat1}, {lon1}) -> ({lat2}, {lon2})")
        return float('inf')
    try:
        R = 3959  # miles
        lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c
    except Exception as e:
        log_debug(f"[WARN] Error in calculate_distance: {e}")
        return float('inf')


def find_nearby_stops(
    lat: float,
    lon: float,
    stops: List[Dict[str, Any]],
    radius_miles: float = 0.15,
    limit: int = 5
) -> List[Dict[str, Any]]:
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


def find_nearby_stops_minimal(
    lat: float,
    lon: float,
    stops: List[Dict[str, Any]],
    radius_miles: float = 0.15,
    limit: int = 10
) -> List[Dict[str, Any]]:
    nearby_stops = []
    for stop in stops:
        distance = calculate_distance(lat, lon, stop["stop_lat"], stop["stop_lon"])
        if distance <= radius_miles:
            nearby_stops.append({
                "stop_id": stop["stop_id"],
                "stop_code": stop.get("stop_code"),
                "stop_name": stop["stop_name"],
                "stop_lat": stop["stop_lat"],
                "stop_lon": stop["stop_lon"],
                "agency": stop["agency"],
                "distance_miles": round(distance, 2)
            })

    nearby_stops.sort(key=lambda x: x["distance_miles"])
    return nearby_stops[:limit]


def get_nearby_stops(lat: float, lon: float, radius: float = 0.15, limit: int = 10) -> List[Dict[str, Any]]:
    log_debug(f"[Unified] Searching for nearby stops from all agencies at ({lat}, {lon})")

    all_nearby = []
    for agency in settings.AGENCY_ID:
        normalized = settings.normalize_agency(agency)
        stops = load_stops(normalized)
        if not stops:
            continue
        nearby = find_nearby_stops_minimal(lat, lon, stops, radius, limit)
        all_nearby.extend(nearby)

    all_nearby.sort(key=lambda x: x["distance_miles"])
    return all_nearby[:limit]


def load_stops(agency: str) -> List[Dict[str, Any]]:
    try:
        service = GTFSService(agency)
        stops_df = service.get_stops()
        if stops_df.empty:
            log_debug(f"✗ GTFS stops table is empty for agency: {agency}")
            return []

        stops = []
        for _, row in stops_df.iterrows():
            stop = {
                "stop_id": row["stop_id"],
                "stop_name": row["stop_name"],
                "stop_lat": float(row["stop_lat"]),
                "stop_lon": float(row["stop_lon"]),
                "agency": agency,
                "stop_code": str(row["stop_code"]) if "stop_code" in row and row["stop_code"] else None
            }
            stops.append(stop)

        log_debug(f"✓ Loaded {len(stops)} stops for agency: {agency}")
        return stops

    except Exception as e:
        log_debug(f"✗ Error loading stops for {agency}: {str(e)}")
        return []
