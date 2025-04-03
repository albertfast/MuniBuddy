import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session, sessionmaker
import json
import requests
from datetime import datetime
from redis import Redis
from geopy.distance import great_circle
from app.db.database import get_db
from app.models.bus_route import BusRoute
import networkx as nx
from geopy.geocoders import Nominatim
from sqlalchemy.sql import text 
from app.config import settings
routes_df, trips_df, stops_df, stop_times_df, calendar_df = settings.gtfs_data

API_KEY = settings.API_KEY
REDIS_HOST = settings.REDIS_HOST
REDIS_PORT = settings.REDIS_PORT
print(f"[DEBUG] Redis: {REDIS_HOST}:{REDIS_PORT}")

# Database connection
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

router = APIRouter()
G = nx.DiGraph()

# Initialize Redis cache
redis = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

@router.get("/optimized-route", tags=["Best Route"])

def load_gtfs_data():
    """Loads GTFS data and displays summary information."""
    print("Loading GTFS data...")
    db = SessionLocal()
    
    try:
        # Load routes
        routes_query = text("SELECT COUNT(*) FROM routes;")
        routes_count = db.execute(routes_query).scalar()
        print(f"Loaded routes: {routes_count}")
        
        # Load stops
        stops_query = text("SELECT COUNT(*) FROM stops;")
        stops_count = db.execute(stops_query).scalar()
        print(f"Loaded stops: {stops_count}")
        
        # Load stop times
        stop_times_query = text("SELECT COUNT(*) FROM stop_times;")
        stop_times_count = db.execute(stop_times_query).scalar()
        print(f"Loaded stop_times: {stop_times_count}")
        
        # Load trips
        trips_query = text("SELECT COUNT(*) FROM trips;")
        trips_count = db.execute(trips_query).scalar()
        print(f"Loaded trips: {trips_count}")
        
        return routes_count, stops_count, stop_times_count, trips_count
        
    except Exception as e:
        print(f"Error loading GTFS data: {str(e)}")
        raise
    finally:
        db.close()

@router.get("/optimized-route")
def find_optimized_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float, db: Session = Depends(get_db)
):
    """Finds the best transit route using GTFS + 511 API + A* heuristic."""
    
    cache_key = f"route:{start_lat},{start_lon}-{end_lat},{end_lon}"
    cached_route = redis.get(cache_key)
    if cached_route:
        return json.loads(cached_route)  # Return cached route if available

    # Step 1: Find nearest transit stops
    start_stop = find_nearest_stop(start_lat, start_lon, db)
    end_stop = find_nearest_stop(end_lat, end_lon, db)
    if not start_stop or not end_stop:
        raise HTTPException(status_code=404, detail="No nearby stops found.")

    # Step 2: Fetch real-time bus data
    live_buses = get_live_bus_positions()
    if not live_buses:
        raise HTTPException(status_code=500, detail="Live data unavailable.")
    
    # Step 3: Use A* search to find best route
    best_route = a_star_search(start_stop, end_stop, live_buses, db)
    if not best_route:
        raise HTTPException(status_code=404, detail="No optimal route found.")
    
    redis.setex(cache_key, 300, json.dumps(best_route))  # Cache for 5 minutes
    return best_route

def build_graph(db):
    """Creates graph structure from database data."""
    global G
    G.clear()  # Clear previous graph

    # 1. Add stops
    stops_query = text("SELECT stop_id, stop_lat, stop_lon FROM stops;")
    stops = db.execute(stops_query).fetchall()
    
    for stop in stops:
        G.add_node(stop[0], pos=(stop[1], stop[2]))  # (stop_id, (lat, lon))

    # 2. Add routes
    routes_query = text("SELECT from_stop, to_stop, travel_time FROM transit_edges;")
    edges = db.execute(routes_query).fetchall()

    for edge in edges:
        G.add_edge(edge[0], edge[1], weight=edge[2], type="transit")

    print(f"✅ Graph created! Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")

def find_nearest_stop(lat: float, lon: float, db: Session):
    """Finds the nearest transit stop using PostGIS distance function."""
    print(f"[DEBUG] Searching for nearest stop to coordinates: {lat}, {lon}")
    
    query = text("""
        SELECT stop_id, stop_name, stop_lat, stop_lon, 
               ST_Distance(geog::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)/1000 AS distance
        FROM stops
        WHERE geog IS NOT NULL
        ORDER BY geog <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
        LIMIT 1;
    """)
    
    try:
        result = db.execute(query, {"lat": lat, "lon": lon}).fetchone()
        print(f"[DEBUG] Query result: {result}")
        
        if result:
            stop_data = {
                "stop_id": result[0],
                "stop_name": result[1],
                "lat": result[2],
                "lon": result[3],
                "distance": result[4]
            }
            print(f"[DEBUG] Found stop: {stop_data}")
            return stop_data
        
        print("[DEBUG] No stops found")
        return None  # If no stop is found
        
    except Exception as e:
        print(f"[DEBUG] Error in find_nearest_stop: {str(e)}")
        raise

def get_live_bus_positions():
    """Fetches real-time bus positions from 511 API."""
    try:
        url = f"http://api.511.org/transit/VehicleMonitoring?api_key={API_KEY}&agency=SF"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"[DEBUG] API error: {response.status_code}")
            return []
            
        # Clean UTF-8-BOM character
        text = response.text.encode().decode('utf-8-sig')
        data = json.loads(text)
        
        vehicles = data.get("Siri", {}).get("ServiceDelivery", {}).get("VehicleMonitoringDelivery", [{}])[0].get("VehicleActivity", [])
        print(f"[DEBUG] Found {len(vehicles)} active vehicles")
        return vehicles
        
    except Exception as e:
        print(f"[DEBUG] Error fetching live bus positions: {str(e)}")
        return []  # Return empty list in case of API error

def a_star_search(start_stop, end_stop, live_buses, db):
    """Finds route using A* algorithm."""
    print(f"\nSearching route: {start_stop['stop_id']} -> {end_stop['stop_id']}")
    
    # Get coordinates of start and end points
    start_lat, start_lon = start_stop['lat'], start_stop['lon']
    end_lat, end_lon = end_stop['lat'], end_stop['lon']
    
    # Calculate initial distance to destination
    initial_distance_km = great_circle(
        (start_lat, start_lon),
        (end_lat, end_lon)
    ).kilometers
    initial_distance_mi = initial_distance_km * 0.621371
    print(f"Initial distance to destination: {initial_distance_mi:.2f} mi")
    
    # Find routes passing through start point
    start_routes = get_routes_for_stop(start_stop['stop_id'], db)
    
    if not start_routes:
        print("No routes found passing through start point!")
        return None
    
    current_day = datetime.now().weekday()
    is_weekend = current_day >= 5
    print(f"Day: {'Weekend' if is_weekend else 'Weekday'}")
    
    # Format route information
    route_info = []
    for route in start_routes:
        route_info.append(f"{route['route_id']} ({route['route_name']})")
    print(f"Found routes: {route_info}")
    
    # Calculate distance to destination for each route
    best_route = None
    min_distance = float('inf')
    best_route_id = None
    best_route_name = None
    
    for route in start_routes:
        # Get stops for this route
        path = get_stops_for_route(route['route_id'], start_stop['stop_id'], end_stop['stop_id'], db)
        if path and len(path) > 1:  # Make sure we have at least 2 stops
            # Calculate total distance of the route
            total_distance = 0
            for i in range(len(path) - 1):
                # Get coordinates of consecutive stops
                stop1_query = text("SELECT stop_lat, stop_lon FROM stops WHERE stop_id = :stop_id")
                stop2_query = text("SELECT stop_lat, stop_lon FROM stops WHERE stop_id = :stop_id")
                
                stop1 = db.execute(stop1_query, {"stop_id": path[i]}).fetchone()
                stop2 = db.execute(stop2_query, {"stop_id": path[i+1]}).fetchone()
                
                if stop1 and stop2:
                    # Use great_circle for more accurate distance calculation
                    total_distance += great_circle(
                        (stop1[0], stop1[1]),
                        (stop2[0], stop2[1])
                    ).kilometers
            
            # Add distance from last stop to destination
            last_stop_query = text("SELECT stop_lat, stop_lon FROM stops WHERE stop_id = :stop_id")
            last_stop = db.execute(last_stop_query, {"stop_id": path[-1]}).fetchone()
            if last_stop:
                final_distance = great_circle(
                    (last_stop[0], last_stop[1]),
                    (end_lat, end_lon)
                ).kilometers
                total_distance += final_distance
                
                # Consider all routes, but prefer those with shorter total distance
                if total_distance < min_distance:
                    min_distance = total_distance
                    best_route = path
                    best_route_id = route['route_id']
                    best_route_name = route['route_name']
    
    if not best_route:
        print("No suitable route found!")
        return None
    
    print(f"Selected route: {best_route_id} ({best_route_name})")
    print(f"Route found! ({len(best_route)} stops)")
    print(f"Total distance: {min_distance * 0.621371:.2f} mi")
    return best_route

def calculate_direction(start_lat, start_lon, end_lat, end_lon):
    """Calculates direction between two points."""
    # Simple direction calculation: East-West and North-South
    if end_lon > start_lon:
        return 'east'
    elif end_lon < start_lon:
        return 'west'
    elif end_lat > start_lat:
        return 'north'
    else:
        return 'south'

def get_next_stops_in_direction(stop_id, route_id, direction, db):
    """Finds the next stops in a given direction."""
    query = text("""
        WITH route_stops AS (
            SELECT st.stop_id, s.stop_lat, s.stop_lon,
                   st.stop_sequence, t.direction_id
            FROM stop_times st
            JOIN trips t ON st.trip_id = t.trip_id
            JOIN stops s ON st.stop_id = s.stop_id
            WHERE t.route_id = :route_id
            ORDER BY st.stop_sequence
        )
        SELECT stop_id, stop_lat, stop_lon, stop_sequence, direction_id
        FROM route_stops
        WHERE stop_id = :stop_id
        LIMIT 1;
    """)
    
    current_stop = db.execute(query, {"route_id": route_id, "stop_id": stop_id}).fetchone()
    if not current_stop:
        return []
    
    # Find next stops based on direction
    if direction in ['east', 'west']:
        next_stops_query = text("""
            WITH route_stops AS (
                SELECT st.stop_id, s.stop_lat, s.stop_lon,
                       st.stop_sequence, t.direction_id
                FROM stop_times st
                JOIN trips t ON st.trip_id = t.trip_id
                JOIN stops s ON st.stop_id = s.stop_id
                WHERE t.route_id = :route_id
                AND t.direction_id = :direction_id
                ORDER BY st.stop_sequence
            )
            SELECT stop_id, stop_lat, stop_lon, stop_sequence, direction_id
            FROM route_stops
            WHERE stop_sequence > :current_sequence
            ORDER BY stop_sequence
            LIMIT 5;
        """)
    else:
        next_stops_query = text("""
            WITH route_stops AS (
                SELECT st.stop_id, s.stop_lat, s.stop_lon,
                       st.stop_sequence, t.direction_id
                FROM stop_times st
                JOIN trips t ON st.trip_id = t.trip_id
                JOIN stops s ON st.stop_id = s.stop_id
                WHERE t.route_id = :route_id
                AND t.direction_id = :direction_id
                ORDER BY st.stop_sequence
            )
            SELECT stop_id, stop_lat, stop_lon, stop_sequence, direction_id
            FROM route_stops
            WHERE stop_sequence < :current_sequence
            ORDER BY stop_sequence DESC
            LIMIT 5;
        """)
    
    next_stops = db.execute(next_stops_query, {
        "route_id": route_id,
        "direction_id": current_stop.direction_id,
        "current_sequence": current_stop.stop_sequence
    }).fetchall()
    
    return next_stops

def select_best_route(routes, end_lat, end_lon, db):
    """Selects the route heading closest to the destination."""
    best_route = None
    min_distance = float('inf')
    
    for route in routes:
        for stop in route['next_stops']:
            distance = calculate_distance(stop.stop_lat, stop.stop_lon, end_lat, end_lon)
            if distance < min_distance:
                min_distance = distance
                best_route = route
    
    return best_route

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates distance between two points."""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth's radius (km)
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def build_transit_graph():
    """Creates transit graph."""
    print("Building transit graph...")
    db = SessionLocal()
    
    try:
        # Add stops
        stops_query = text("SELECT stop_id, stop_lat, stop_lon FROM stops;")
        stops = db.execute(stops_query).fetchall()
        
        # First store all stops in a dictionary
        stop_positions = {}
        for stop in stops:
            stop_id, lat, lon = stop
            G.add_node(stop_id, pos=(lat, lon))
            stop_positions[stop_id] = (lat, lon)
        
        print(f"Added {len(G.nodes)} nodes to graph")
        
        # Add routes
        routes_query = text("SELECT from_stop, to_stop, travel_time FROM transit_edges;")
        edges = db.execute(routes_query).fetchall()
        
        for edge in edges:
            G.add_edge(edge[0], edge[1], weight=edge[2], type="transit")
        
        print(f"Added {len(G.edges)} transit edges to graph")
        
        # Create walking edges in memory
        walking_edges = []
        MAX_WALKING_DISTANCE = 2.0  # Maximum walking distance in km
        
        # Calculate walking distance for each stop pair
        for stop1_id, pos1 in stop_positions.items():
            for stop2_id, pos2 in stop_positions.items():
                if stop1_id != stop2_id:
                    distance = great_circle(pos1, pos2).kilometers
                    if distance <= MAX_WALKING_DISTANCE:
                        # Walking speed: 5 km/h = 12 minutes/km
                        walking_time = distance * 12  # in minutes
                        G.add_edge(stop1_id, stop2_id, weight=walking_time, type="walking")
                        walking_edges.append((stop1_id, stop2_id, distance))
        
        print(f"Added {len(walking_edges)} walking edges to graph")
        
        # Check graph connectivity
        components = list(nx.connected_components(G.to_undirected()))
        print(f"Number of connected components: {len(components)}")
        print(f"Size of largest component: {len(max(components, key=len))}")
        
    except Exception as e:
        print(f"Error building transit graph: {str(e)}")
        raise
    finally:
        db.close()

def find_route(start_stop, end_stop, db):
    """Finds the shortest route between two stops."""
    print(f"Finding route from {start_stop['stop_id']} to {end_stop['stop_id']}...")
    
    try:
        # Find route using A* algorithm
        path = a_star_search(start_stop, end_stop, get_live_bus_positions(), db)
        
        if path:
            print(f"Found path with {len(path)} stops")
            
            # Calculate distances between consecutive stops
            print("\n                 🚌 Stop Details                 ")
            print("┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓")
            print("┃ Stop ┃ Stop Name              ┃ Distance (mi) ┃")
            print("┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩")
            
            prev_stop = None
            total_distance = 0
            
            for stop_id in path:
                stop_query = text("SELECT stop_name, stop_lat, stop_lon FROM stops WHERE stop_id = :stop_id")
                stop = db.execute(stop_query, {"stop_id": stop_id}).fetchone()
                
                if prev_stop:
                    # Calculate distance between consecutive stops
                    segment_distance = great_circle(
                        (prev_stop[1], prev_stop[2]),  # lat, lon of previous stop
                        (stop[1], stop[2])  # lat, lon of current stop
                    ).miles
                    total_distance += segment_distance
                    print(f"│ {stop_id} │ {stop[0]:<20} │ {segment_distance:>11.2f} │")
                else:
                    print(f"│ {stop_id} │ {stop[0]:<20} │ {0:>11.2f} │")
                
                prev_stop = stop
            
            print("└──────┴────────────────────────┴───────────────┘")
            print(f"\nTotal distance: {total_distance:.2f} miles")
            
            return path
        else:
            print("No path found!")
            return None
            
    except Exception as e:
        print(f"Error finding route: {str(e)}")
        return None

def get_routes_for_stop(stop_id, db):
    """Finds routes passing through a stop."""
    # Check weekday/weekend
    current_day = datetime.now().weekday()  # 0-6 (Monday-Sunday)
    is_weekend = current_day >= 5  # Saturday (5) or Sunday (6)
    
    query = text("""
        SELECT DISTINCT r.route_id, r.route_type
        FROM routes r
        JOIN trips t ON r.route_id = t.route_id
        JOIN stop_times st ON t.trip_id = st.trip_id
        WHERE st.stop_id = :stop_id
        AND (
            (:is_weekend = true AND r.route_id = '5')  -- Weekend 5
            OR
            (:is_weekend = false AND r.route_id = '5R')  -- Weekday 5R
        );
    """)
    
    routes = db.execute(query, {
        "stop_id": stop_id,
        "is_weekend": is_weekend
    }).fetchall()
    
    if not routes:
        # If no specific route found, get all routes
        fallback_query = text("""
            SELECT DISTINCT r.route_id, r.route_type
            FROM routes r
            JOIN trips t ON r.route_id = t.route_id
            JOIN stop_times st ON t.trip_id = st.trip_id
            WHERE st.stop_id = :stop_id;
        """)
        routes = db.execute(fallback_query, {"stop_id": stop_id}).fetchall()
    
    return [{
        "route_id": route.route_id,
        "route_type": route.route_type,
        "route_name": f"Route {route.route_id}"  # Use route_id as name since we don't have route_name
    } for route in routes]

def get_stops_for_route(route_id, start_stop_id, end_stop_id, db):
    """Finds stops for a given route."""
    # Get coordinates of start and end stops
    coords_query = text("""
        SELECT s.stop_lat, s.stop_lon, s.stop_name
        FROM stops s
        WHERE s.stop_id IN (:start_stop_id, :end_stop_id);
    """)
    
    coords = db.execute(coords_query, {
        "start_stop_id": start_stop_id,
        "end_stop_id": end_stop_id
    }).fetchall()
    
    if len(coords) != 2:
        print("Could not find coordinates for start or end stop")
        return None
    
    start_lat, start_lon = coords[0][0], coords[0][1]
    end_lat, end_lon = coords[1][0], coords[1][1]
    
    # Calculate direction from start to end
    direction = calculate_direction(start_lat, start_lon, end_lat, end_lon)
    print(f"Direction to destination: {direction}")
    
    # Get all stops for this route
    stops_query = text("""
        WITH route_stops AS (
            SELECT DISTINCT st.stop_id, s.stop_lat, s.stop_lon,
                   st.stop_sequence, t.direction_id, s.stop_name,
                   ROW_NUMBER() OVER (PARTITION BY st.stop_id ORDER BY st.stop_sequence) as rn
            FROM stop_times st
            JOIN trips t ON st.trip_id = t.trip_id
            JOIN stops s ON st.stop_id = s.stop_id
            WHERE t.route_id = :route_id
            ORDER BY st.stop_sequence
        )
        SELECT stop_id, stop_lat, stop_lon, stop_sequence, direction_id, stop_name
        FROM route_stops
        WHERE rn = 1
        ORDER BY stop_sequence;
    """)
    
    stops = db.execute(stops_query, {
        "route_id": route_id
    }).fetchall()
    
    if not stops:
        print(f"No stops found for route {route_id}")
        return None
    
    print(f"\nAll 5R stops:")
    print("┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓")
    print("┃ Stop ┃ Stop Name              ┃ Distance (mi) ┃")
    print("┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩")
    
    # Find the best stop to get off based on distance to destination
    best_stop = None
    min_distance = float('inf')
    path = []
    seen_stops = set()
    
    for stop in stops:
        if stop.stop_id not in seen_stops:
            seen_stops.add(stop.stop_id)
            
            # Calculate distance to destination
            distance_mi = great_circle(
                (stop.stop_lat, stop.stop_lon),
                (end_lat, end_lon)
            ).miles
            
            print(f"│ {stop.stop_id} │ {stop.stop_name:<20} │ {distance_mi:>11.2f} │")
            
            # Consider all stops after start_stop_id
            if stop.stop_id == start_stop_id:
                path.append(stop.stop_id)
                continue
                
            if len(path) > 0:  # Only consider stops after we've found the start stop
                path.append(stop.stop_id)
                if distance_mi < min_distance:
                    min_distance = distance_mi
                    best_stop = stop
    
    print("└──────┴────────────────────────┴───────────────┘")
    
    if not best_stop:
        print("Could not find a suitable stop to get off")
        return None
    
    print(f"\nBest stop to get off: {best_stop.stop_name} ({best_stop.stop_id})")
    print(f"Distance to destination: {min_distance:.2f} miles")
    
    # Create final path from start to best stop
    final_path = []
    for stop_id in path:
        final_path.append(stop_id)
        if stop_id == best_stop.stop_id:
            break
    
    print(f"\nTotal number of stops: {len(final_path)}")
    return final_path

def calculate_angle(lat1, lon1, lat2, lon2, lat3, lon3):
    """Calculates the angle between two vectors in degrees."""
    from math import atan2, degrees, pi
    
    # Calculate vectors
    v1_lat = lat2 - lat1
    v1_lon = lon2 - lon1
    v2_lat = lat3 - lat1
    v2_lon = lon3 - lon1
    
    # Calculate angles
    angle1 = atan2(v1_lon, v1_lat)
    angle2 = atan2(v2_lon, v2_lat)
    
    # Calculate difference
    angle_diff = abs(angle1 - angle2)
    
    # Convert to degrees and normalize to 0-180
    angle_deg = degrees(angle_diff)
    if angle_deg > 180:
        angle_deg = 360 - angle_deg
    
    # Adjust angle based on direction
    if v1_lon > 0 and v2_lon < 0:  # Going east vs west
        angle_deg = 180 - angle_deg
    elif v1_lon < 0 and v2_lon > 0:  # Going west vs east
        angle_deg = 180 - angle_deg
    elif v1_lat > 0 and v2_lat < 0:  # Going north vs south
        angle_deg = 180 - angle_deg
    elif v1_lat < 0 and v2_lat > 0:  # Going south vs north
        angle_deg = 180 - angle_deg
    
    return angle_deg
