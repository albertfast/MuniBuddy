from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text 
from sqlalchemy.orm import Session
import json
import requests
from datetime import datetime
from redis import Redis
from geopy.distance import great_circle
from app.database  import get_db
from app.models.bus_route import BusRoute
import networkx as nx
from geopy.geocoders import Nominatim
from sqlalchemy.sql import text 
from app.config import settings
API_KEY = settings.API_KEY
REDIS_HOST = settings.REDIS_HOST
REDIS_PORT = settings.REDIS_PORT
print(f"[DEBUG] API_KEY: {API_KEY}, Redis: {REDIS_HOST}:{REDIS_PORT}")

router = APIRouter()
G = nx.DiGraph()

# Initialize Redis cache
redis = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

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
    """Veritabanından verileri alarak graf yapısını oluşturur."""
    global G
    G.clear()  # Önceki grafı temizle

    # 1. Durakları ekle
    stops_query = text("SELECT stop_id, stop_lat, stop_lon FROM stops;")  # 🔥 text() içine al
    stops = db.execute(stops_query).fetchall()
    
    for stop in stops:
        G.add_node(stop[0], pos=(stop[1], stop[2]))  # (stop_id, (lat, lon))

    # 2. Rotaları ekle
    routes_query = text("SELECT from_stop, to_stop, travel_time FROM transit_edges;")  # 🔥 text() içine al
    edges = db.execute(routes_query).fetchall()

    for edge in edges:
        G.add_edge(edge[0], edge[1], weight=edge[2], type="transit")

    print(f"✅ Graph oluşturuldu! Düğümler: {len(G.nodes)}, Kenarlar: {len(G.edges)}")

def find_nearest_stop(lat: float, lon: float, db: Session):
    """Finds the nearest transit stop using PostGIS distance function."""
    query = """
        SELECT stop_id, stop_name, stop_lat, stop_lon, 
               ST_Distance(geog, ST_MakePoint(:lon, :lat)::geography) AS distance
        FROM stops
        ORDER BY distance ASC
        LIMIT 1;
    """
    result = db.execute(query, {"lat": lat, "lon": lon}).fetchone()
    
    if result:
        return {
            "stop_id": result[0],
            "stop_name": result[1],
            "lat": result[2],
            "lon": result[3],
            "distance": result[4]
        }
    
    return None  # Eğer durak bulunamazsa


def get_live_bus_positions():
    """Fetches real-time bus positions from 511 API."""
    url = f"http://api.511.org/transit/VehicleMonitoring?api_key={API_KEY}&agency=SF"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data.get("Siri", {}).get("ServiceDelivery", {}).get("VehicleMonitoringDelivery", {}).get("VehicleActivity", [])


def a_star_search(start_stop, end_stop, live_buses, db: Session):
    """Performs A* search with landmark heuristics."""
    open_set = [(0, start_stop["stop_id"])]
    came_from = {}
    g_score = {start_stop["stop_id"]: 0}
    
    while open_set:
        current_cost, current_stop = min(open_set)
        open_set.remove((current_cost, current_stop))
        
        if current_stop == end_stop["stop_id"]:
            return reconstruct_path(came_from, current_stop)
        
        neighbors = get_neighbors(current_stop, live_buses, db)
        for neighbor, travel_cost in neighbors:
            tentative_g_score = g_score[current_stop] + travel_cost
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                g_score[neighbor] = tentative_g_score
                open_set.append((tentative_g_score, neighbor))
                came_from[neighbor] = current_stop
    
    return None


def get_neighbors(stop_id, live_buses, db):
    """Fetches neighboring stops and real-time transit options."""
    neighbors = []
    query = """
        SELECT to_stop, travel_time FROM transit_edges WHERE from_stop = :stop_id
    """
    results = db.execute(query, {"stop_id": stop_id}).fetchall()
    for result in results:
        neighbors.append((result["to_stop"], result["travel_time"]))
    
    # Add real-time transit options
    for bus in live_buses:
        bus_stop = bus["MonitoredVehicleJourney"].get("MonitoredCall", {}).get("StopPointRef")
        if bus_stop and bus_stop == stop_id:
            neighbors.append((bus_stop, 0))  # Bus already at stop
    
    return neighbors


def reconstruct_path(came_from, current_stop):
    """Reconstructs the shortest path from the search tree."""
    path = [current_stop]
    while current_stop in came_from:
        current_stop = came_from[current_stop]
        path.append(current_stop)
    return path[::-1]
