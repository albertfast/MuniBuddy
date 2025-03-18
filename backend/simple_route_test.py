import os
import logging
import networkx as nx
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@localhost:5432/munibuddy_db")

def create_test_graph():
    """Create a small test graph if database connection fails"""
    G = nx.DiGraph()
    
    # Add some nodes (stops)
    stops = [
        ("stop1", "Golden Gate Park", 37.7694, -122.4862),
        ("stop2", "Haight Street", 37.7692, -122.4481),
        ("stop3", "Castro District", 37.7609, -122.4350),
        ("stop4", "Mission District", 37.7599, -122.4148),
        ("stop5", "Union Square", 37.7881, -122.4075),
        ("stop6", "Financial District", 37.7946, -122.3999),
        ("stop7", "Fisherman's Wharf", 37.8081, -122.4166)
    ]
    
    for stop_id, name, lat, lon in stops:
        G.add_node(stop_id, name=name, lat=lat, lon=lon)
    
    # Add connections between stops
    edges = [
        ("stop1", "stop2", 5, "1"),  # Golden Gate Park to Haight
        ("stop2", "stop3", 7, "1"),  # Haight to Castro
        ("stop3", "stop4", 6, "2"),  # Castro to Mission
        ("stop4", "stop5", 8, "2"),  # Mission to Union Square
        ("stop5", "stop6", 4, "3"),  # Union Square to Financial
        ("stop6", "stop7", 7, "3"),  # Financial to Fisherman's
        ("stop2", "stop5", 12, "4")  # Haight to Union Square (express)
    ]
    
    for from_stop, to_stop, time, route_id in edges:
        G.add_edge(from_stop, to_stop, travel_time=time, route_id=route_id)
    
    return G

def find_path(G, start_stop, end_stop):
    """Find path between stops and return serializable results"""
    try:
        # Use A* search
        path = nx.astar_path(G, start_stop, end_stop, weight='travel_time')
        
        # Create a serializable result
        result = []
        total_time = 0
        last_route_id = None
        
        for i in range(len(path)):
            stop_id = path[i]
            node_data = G.nodes[stop_id]
            
            # Get stop info
            stop_info = {
                "id": stop_id,
                "name": node_data.get("name", "Unknown"),
                "lat": node_data.get("lat", 0),
                "lon": node_data.get("lon", 0)
            }
            
            # Add route info for edges
            if i < len(path) - 1:
                next_stop = path[i+1]
                edge_data = G[stop_id][next_stop]
                route_id = edge_data.get("route_id", "Unknown")
                travel_time = edge_data.get("travel_time", 0)
                
                stop_info["next_route_id"] = route_id
                stop_info["travel_time_to_next"] = travel_time
                total_time += travel_time
                
                # Check if this is a transfer point
                if last_route_id is not None and last_route_id != route_id:
                    stop_info["is_transfer"] = True
                
                last_route_id = route_id
            
            result.append(stop_info)
        
        return {
            "success": True,
            "route": result,
            "total_time": total_time,
            "stops_count": len(result)
        }
        
    except nx.NetworkXNoPath:
        return {
            "success": False,
            "error": "No path found between stops"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def find_nearest_stop(G, lat, lon):
    """Find nearest stop to given coordinates"""
    min_dist = float('inf')
    nearest_stop = None
    
    for stop_id, data in G.nodes(data=True):
        if "lat" in data and "lon" in data:
            dist = ((data["lat"] - lat)**2 + (data["lon"] - lon)**2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                nearest_stop = stop_id
    
    return nearest_stop

def main():
    """Test route finding with sample coordinates"""
    # Try to build graph from database or use test graph
    try:
        from route_finder2 import build_graph, G
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        logger.info("Building graph from database...")
        build_graph(db)
        logger.info(f"Graph built with {len(G.nodes)} nodes and {len(G.edges)} edges")
        db.close()
    except Exception as e:
        logger.warning(f"Failed to build graph from database: {e}")
        logger.info("Using test graph instead")
        G = create_test_graph()
        logger.info(f"Test graph created with {len(G.nodes)} nodes and {len(G.edges)} edges")
    
    # Test coordinates
    test_cases = [
        {
            "name": "Golden Gate Park to Fisherman's Wharf",
            "start_lat": 37.7694,
            "start_lon": -122.4862,
            "end_lat": 37.8081,
            "end_lon": -122.4166
        },
        {
            "name": "Mission to Financial District",
            "start_lat": 37.7599,
            "start_lon": -122.4148,
            "end_lat": 37.7946,
            "end_lon": -122.3999
        }
    ]
    
    # Run tests
    for test in test_cases:
        logger.info(f"\nTesting route: {test['name']}")
        
        # Find nearest stops
        start_stop = find_nearest_stop(G, test["start_lat"], test["start_lon"])
        end_stop = find_nearest_stop(G, test["end_lat"], test["end_lon"])
        
        if not start_stop or not end_stop:
            logger.error("Could not find nearest stops")
            continue
            
        logger.info(f"Start stop: {start_stop}")
        logger.info(f"End stop: {end_stop}")
        
        # Find path
        result = find_path(G, start_stop, end_stop)
        
        # Print results
        if result["success"]:
            logger.info(f"✅ Route found with {len(result['route'])} stops, total time: {result['total_time']} minutes")
            for i, stop in enumerate(result["route"]):
                route_info = f" → {stop.get('next_route_id', '')}" if i < len(result["route"]) - 1 else ""
                transfer = " [Transfer!]" if stop.get("is_transfer") else ""
                logger.info(f"  {i+1}. {stop['name']}{route_info}{transfer}")
        else:
            logger.error(f"❌ No route found: {result.get('error', 'Unknown error')}")
        
        # Make sure result is JSON serializable
        try:
            json_result = json.dumps(result)
            logger.info("✅ Result is JSON serializable")
        except (TypeError, ValueError) as e:
            logger.error(f"❌ Result is not JSON serializable: {e}")

if __name__ == "__main__":
    main()