from app.services.debug_logger import log_debug
import pandas as pd
import math
from typing import List, Dict, Any
from datetime import datetime
import pandas as pd
# from colorama import Fore, Style
from app.services.debug_logger import log_debug

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.
    Returns distance in miles.
    """
    from app.services.debug_logger import log_debug
    import math

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
        log_debug(f"[WARN] Error in _calculate_distance: {e}")
        return float('inf')

async def load_stops(self) -> List[Dict[str, Any]]:
    """
    Load all stops from GTFS data.

    Returns:
        List[Dict[str, Any]]: List of stops with their coordinates
    """
    if self.stops_cache is not None:
        return self.stops_cache

    try:
        stops = []
        for agency in ["muni", "bart"]:
            if agency in self.gtfs_data and 'stops' in self.gtfs_data[agency]:
                agency_stops = self.gtfs_data[agency]['stops']
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

        self.stops_cache = stops
        log_debug(f"✓ Loaded {len(stops)} stops from GTFS data")
        return stops

    except Exception as e:
        log_debug(f"✗ Error loading stops: {str(e)}")
        return []


async def find_nearby_stops(self, lat: float, lon: float, radius_miles: float = 0.1, limit: int = 3) -> List[Dict[str, Any]]:
    stops = await self._load_stops()
    nearby_stops = []

    for stop in stops:
        distance = self._calculate_distance(lat, lon, stop['stop_lat'], stop['stop_lon'])
        if distance <= radius_miles:
            stop_id = stop['stop_id']
            agency = stop.get('agency', 'muni')

            try:
                gtfs_stop_id = stop_id
                if agency == 'muni' and not stop_id.startswith('1'):
                    gtfs_stop_id = f"1{stop_id}"
                    log_debug(f"ℹ️ Converting stop ID {stop_id} to GTFS format: {gtfs_stop_id}")

                if agency in self.gtfs_data and 'stop_times' in self.gtfs_data[agency]:
                    stop_times = self.gtfs_data[agency]['stop_times']
                    stop_times = stop_times[stop_times['stop_id'] == gtfs_stop_id]

                    if not stop_times.empty:
                        weekday = datetime.now().strftime("%A").lower()
                        calendar_df = self.gtfs_data[agency]['calendar']
                        active_services = calendar_df[
                            (calendar_df[weekday] == 1) &
                            (pd.to_numeric(calendar_df['start_date']) <= int(datetime.now().strftime("%Y%m%d"))) &
                            (pd.to_numeric(calendar_df['end_date']) >= int(datetime.now().strftime("%Y%m%d")))
                        ]['service_id']

                        active_trips = self.gtfs_data[agency]['trips']
                        active_trips = active_trips[active_trips['service_id'].isin(active_services)]

                        valid_trips = stop_times.merge(
                            active_trips[['trip_id', 'route_id', 'direction_id']],
                            on='trip_id'
                        )

                        routes = self.gtfs_data[agency]['routes']
                        routes = routes[routes['route_id'].isin(valid_trips['route_id'])].drop_duplicates()

                        route_info = []
                        for _, route in routes.iterrows():
                            destination = route['route_long_name'].split(' - ')[-1] if ' - ' in route['route_long_name'] else route['route_long_name']
                            route_info.append({
                                'route_id': route['route_id'],
                                'route_number': route['route_short_name'],
                                'destination': destination
                            })

                        log_debug(f"ℹ️ Found {len(route_info)} routes for stop {gtfs_stop_id}: {[r['route_number'] for r in route_info]}")
                    else:
                        route_info = []
                        log_debug(f"⚠️ No stop times found for stop {gtfs_stop_id} ({agency})")
                else:
                    route_info = []

                stop_info = stop.copy()
                stop_info['distance_miles'] = round(distance, 2)
                stop_info['routes'] = route_info
                stop_info['id'] = stop_id
                stop_info['stop_id'] = stop_id
                stop_info['gtfs_stop_id'] = gtfs_stop_id
                nearby_stops.append(stop_info)

            except KeyError as e:
                log_debug(f"⚠ No route data found for stop {stop_id} ({agency}): {e}")
                stop_info = stop.copy()
                stop_info['distance_miles'] = round(distance, 2)
                stop_info['routes'] = []
                stop_info['id'] = stop_id
                stop_info['stop_id'] = stop_id
                stop_info['gtfs_stop_id'] = gtfs_stop_id if 'gtfs_stop_id' in locals() else stop_id
                nearby_stops.append(stop_info)
            except Exception as e:
                log_debug(f"✗ Error while processing stop {stop_id} ({agency}): {e}")
                continue

    nearby_stops.sort(key=lambda x: x['distance_miles'])
    return nearby_stops[:limit]