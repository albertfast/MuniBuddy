from typing import List, Dict, Any, Optional
import math
import pandas as pd

from app.services.debug_logger import log_debug
from app.services.gtfs_service import GTFSService
from app.config import settings


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two lat/lon points using the Haversine formula (in miles)."""
    try:
        R = 3959  # Earth radius in miles
        lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
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
    limit: int = 10,
    minimal: bool = True
) -> List[Dict[str, Any]]:
    """Filter and return nearby stops within a given radius."""
    results = []
    for stop in stops:
        dist = calculate_distance(lat, lon, stop["stop_lat"], stop["stop_lon"])
        if dist <= radius_miles:
            stop_data = {
                "stop_id": stop["stop_id"],
                "stop_code": stop.get("stop_code"),
                "stop_name": stop["stop_name"],
                "stop_lat": stop["stop_lat"],
                "stop_lon": stop["stop_lon"],
                "agency": stop["agency"],
                "distance_miles": round(dist, 2)
            } if minimal else {**stop, "distance_miles": round(dist, 2)}
            results.append(stop_data)

    return sorted(results, key=lambda s: s["distance_miles"])[:limit]


def load_stops(agency: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load stops from GTFS for one or all agencies."""
    try:
        agencies = [agency] if agency else settings.AGENCY_ID
        all_stops = []

        for ag in agencies:
            normalized = settings.normalize_agency(ag)
            service = GTFSService(normalized)
            stops_df = service.get_stops()
            if stops_df.empty:
                log_debug(f"✗ GTFS stops table is empty for agency: {normalized}")
                continue

            for _, row in stops_df.iterrows():
                stop = {
                    "stop_id": row["stop_id"],
                    "stop_name": row["stop_name"],
                    "stop_lat": float(row["stop_lat"]),
                    "stop_lon": float(row["stop_lon"]),
                    "agency": normalized,
                    "stop_code": str(row["stop_code"]) if "stop_code" in row and row["stop_code"] else None
                }
                all_stops.append(stop)

        log_debug(f"✓ Loaded {len(all_stops)} stops for agency={agency or 'ALL'}")
        return all_stops

    except Exception as e:
        log_debug(f"✗ Error loading stops: {str(e)}")
        return []


def get_nearby_stops(lat: float, lon: float, radius: float = 0.15, limit: int = 20) -> List[Dict[str, Any]]:
    """Unified function to get nearby stops across all agencies (if agency not specified)."""
    log_debug(f"[Unified] Searching for nearby stops at ({lat}, {lon}) across all agencies")
    all_nearby = []
    for agency in settings.AGENCY_ID:
        stops = load_stops(agency)
        if not stops:
            continue
        nearby = find_nearby_stops(lat, lon, stops, radius, limit)
        all_nearby.extend(nearby)

    all_nearby.sort(key=lambda x: x["distance_miles"])
    return all_nearby[:limit]