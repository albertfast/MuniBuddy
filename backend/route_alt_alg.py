import networkx as nx
import heapq
import pandas as pd
import os
import time
from geopy.geocoders import Nominatim
from dotenv import load_dotenv

print("Starting script...")

# Load environment variables
load_dotenv()
API_KEY = os.getenv("API_KEY")

# 📍 Geocoder Tanımla
geolocator = Nominatim(user_agent="munibuddy")

# 📂 GTFS Dosya Yolu
GTFS_DIR = os.path.join(os.path.dirname(__file__), "gtfs_data")
ROUTES_FILE = os.path.join(GTFS_DIR, "routes.txt")
STOPS_FILE = os.path.join(GTFS_DIR, "stops.txt")
STOP_TIMES_FILE = os.path.join(GTFS_DIR, "stop_times.txt")
TRIPS_FILE = os.path.join(GTFS_DIR, "trips.txt")

print("Loading GTFS data...")
routes_df = pd.read_csv(ROUTES_FILE, dtype=str)
stops_df = pd.read_csv(STOPS_FILE, dtype=str)
stop_times_df = pd.read_csv(STOP_TIMES_FILE, dtype=str)
trips_df = pd.read_csv(TRIPS_FILE, dtype=str)

print(f"Loaded routes: {len(routes_df)}")
print(f"Loaded stops: {len(stops_df)}")
print(f"Loaded stop_times: {len(stop_times_df)}")
print(f"Loaded trips: {len(trips_df)}")

# ** Durakları Lat-Lon ile Eşleştir **
print("Processing stops...")
stops = {}
for _, row in stops_df.iterrows():
    stops[row['stop_id']] = (float(row['stop_lat']), float(row['stop_lon']))

print(f"Processed {len(stops)} stops")

# ** Otobüs Hatlarına Göre Bağlantıları Kur **
print("Building graph nodes...")
start_time = time.time()
G = nx.DiGraph()
for _, row in stops_df.iterrows():
    stop_id = row['stop_id']
    lat, lon = float(row['stop_lat']), float(row['stop_lon'])
    G.add_node(stop_id, pos=(lat, lon), name=row['stop_name'])

print(f"Added {len(G.nodes)} nodes to graph in {time.time() - start_time:.2f} seconds")

# For efficiency, let's limit to a subset of trips if there are too many
print("Building graph edges...")
start_time = time.time()
edge_count = 0

# Get a list of all unique route IDs
route_ids = routes_df['route_id'].unique()
print(f"Processing {len(route_ids)} routes")

for route_id in route_ids:
    # Get trips for this route
    route_trips = trips_df[trips_df['route_id'] == route_id]
    
    # For debugging, limit to first 10 trips per route
    if len(route_trips) > 20:  # Using more trips for better coverage
        route_trips = route_trips.iloc[:20]
    
    for _, trip in route_trips.iterrows():
        trip_id = trip['trip_id']
        trip_stops = stop_times_df[stop_times_df['trip_id'] == trip_id].sort_values('stop_sequence')
        
        # Connect consecutive stops
        for i in range(len(trip_stops) - 1):
            from_stop = trip_stops.iloc[i]['stop_id']
            to_stop = trip_stops.iloc[i + 1]['stop_id']
            
            if from_stop in stops and to_stop in stops:
                lat1, lon1 = stops[from_stop]
                lat2, lon2 = stops[to_stop]
                
                # Euclidean distance
                distance = ((lat1 - lat2)**2 + (lon1 - lon2)**2) ** 0.5
                
                # Add edge if it doesn't exist or update if shorter path found
                if not G.has_edge(from_stop, to_stop) or G[from_stop][to_stop]['weight'] > distance:
                    G.add_edge(from_stop, to_stop, weight=distance, route_id=route_id, type='transit')
                    edge_count += 1

print(f"Added {edge_count} transit edges to graph in {time.time() - start_time:.2f} seconds")

# ** Add walking connections between nearby stops (max 0.5 km) **
print("Adding walking connections...")
start_time = time.time()
walking_edges = 0
MAX_WALKING_DISTANCE = 0.005  # About 500 meters in lat/lon units

# For efficiency, create a list of stops
stops_list = list(stops.items())

for i, (stop_id1, (lat1, lon1)) in enumerate(stops_list):
    for stop_id2, (lat2, lon2) in stops_list[i+1:]:
        # If stops are different and close enough for walking
        distance = ((lat1 - lat2)**2 + (lon1 - lon2)**2) ** 0.5
        if distance < MAX_WALKING_DISTANCE:
            # Walking is bidirectional
            G.add_edge(stop_id1, stop_id2, weight=distance*1.5, type='walking')  # Walking is slower than transit
            G.add_edge(stop_id2, stop_id1, weight=distance*1.5, type='walking')
            walking_edges += 2

print(f"Added {walking_edges} walking edges to graph in {time.time() - start_time:.2f} seconds")

# Check graph connectivity
print("Checking graph connectivity...")
connected_components = list(nx.weakly_connected_components(G))
print(f"Number of connected components: {len(connected_components)}")
print(f"Size of largest component: {len(max(connected_components, key=len))}")

# Select landmarks (use major transit hubs - stops with most connections)
print("Selecting landmarks...")
node_connections = [(node, len(list(G.neighbors(node)))) for node in G.nodes()]
node_connections.sort(key=lambda x: x[1], reverse=True)
landmarks = [node for node, connections in node_connections[:5]]  # Use top 5 connected nodes

print(f"Selected landmarks: {landmarks}")

# Landmark distances
print("Calculating landmark distances...")
landmark_distances = {}
for landmark in landmarks:
    print(f"Processing landmark {landmark}...")
    start_time = time.time()
    try:
        distances = nx.single_source_dijkstra_path_length(G, landmark, weight='weight')
        landmark_distances[landmark] = distances
        print(f"  Landmark {landmark} connected to {len(distances)} nodes in {time.time() - start_time:.2f} seconds")
    except nx.NetworkXNoPath:
        print(f"  Warning: Landmark {landmark} is not connected to all nodes")

# ** ALT Algoritması (A* + Landmark) **
def alt_algorithm(graph, start, end):
    """ Landmark destekli A* algoritması """
    print(f"Finding path from {start} to {end}...")
    start_time = time.time()
    
    def heuristic(node):
        if not landmarks:
            return 0
        
        h_values = []
        for lm in landmarks:
            if lm in landmark_distances and node in landmark_distances[lm] and end in landmark_distances[lm]:
                h_values.append(abs(landmark_distances[lm][node] - landmark_distances[lm][end]))
        
        return max(h_values) if h_values else 0
    
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    edge_type = {}  # Store the type of edge used (transit or walking)
    g_score = {node: float('inf') for node in graph.nodes}
    g_score[start] = 0
    f_score = {node: float('inf') for node in graph.nodes}
    f_score[start] = heuristic(start)
    
    visited_count = 0
    
    while open_set:
        _, current = heapq.heappop(open_set)
        visited_count += 1
        
        if visited_count % 1000 == 0:
            print(f"  Visited {visited_count} nodes...")
        
        if current == end:
            path = []
            edge_types = []
            while current in came_from:
                path.append(current)
                edge_types.append(edge_type.get((came_from[current], current), 'unknown'))
                current = came_from[current]
            path.append(start)
            path = path[::-1]
            edge_types = edge_types[::-1]
            print(f"Path found with {len(path)} stops in {time.time() - start_time:.2f} seconds")
            return path, edge_types
        
        for neighbor in graph.neighbors(current):
            edge_data = graph[current][neighbor]
            tentative_g_score = g_score[current] + edge_data['weight']
            if tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                edge_type[(current, neighbor)] = edge_data.get('type', 'transit')
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = g_score[neighbor] + heuristic(neighbor)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
    
    print(f"No path found after visiting {visited_count} nodes in {time.time() - start_time:.2f} seconds")
    return None, None  # Yol bulunamazsa

# Function to find nearest stop to a given address
def find_nearest_stop(address):
    print(f"Finding nearest stop for: {address}")
    location = geolocator.geocode(address)
    if not location:
        print(f"Could not geocode address: {address}")
        return None
    
    print(f"Geocoded location: {location.latitude}, {location.longitude}")
    lat, lon = location.latitude, location.longitude
    
    min_distance = float('inf')
    nearest_stop = None
    
    for stop_id, (stop_lat, stop_lon) in stops.items():
        distance = ((lat - stop_lat)**2 + (lon - stop_lon)**2) ** 0.5
        
        if distance < min_distance:
            min_distance = distance
            nearest_stop = stop_id
    
    stop_name = stops_df[stops_df['stop_id'] == nearest_stop]['stop_name'].values[0]
    print(f"Nearest stop: {stop_name} ({nearest_stop}), distance: {min_distance:.6f}")
    return nearest_stop

# Test the algorithm with addresses
start_address = "618 35th ave, San Francisco"
end_address = "520 mason st., San Francisco"

start_stop = find_nearest_stop(start_address)
end_stop = find_nearest_stop(end_address)

if start_stop and end_stop:
    shortest_path, edge_types = alt_algorithm(G, start_stop, end_stop)
    
    # Convert stop_ids to stop names for better readability
    if shortest_path:
        readable_path = []
        for i, stop_id in enumerate(shortest_path):
            stop_name = stops_df[stops_df['stop_id'] == stop_id]['stop_name'].values[0]
            edge_type = edge_types[i-1] if i > 0 else "start"
            prefix = "[🚶 Walking]" if edge_type == 'walking' else "[🚌 Transit]" if edge_type == 'transit' else ""
            readable_path.append(f"{prefix} {stop_name}")
        
        print(f"Başlangıç: {start_address} (Stop ID: {start_stop})")
        print(f"Bitiş: {end_address} (Stop ID: {end_stop})")
        print(f"En kısa yol:")
        for step in readable_path:
            print(f"  - {step}")
        
        # Calculate distance
        total_distance = 0
        transit_segments = 0
        walking_segments = 0
        
        for i in range(len(shortest_path) - 1):
            from_stop = shortest_path[i]
            to_stop = shortest_path[i + 1]
            edge_data = G[from_stop][to_stop]
            total_distance += edge_data['weight']
            
            if edge_data.get('type') == 'transit':
                transit_segments += 1
            elif edge_data.get('type') == 'walking':
                walking_segments += 1
        
        print(f"Toplam mesafe: {total_distance:.4f}")
        print(f"Transit segments: {transit_segments}")
        print(f"Walking segments: {walking_segments}")
    else:
        print(f"No path found between {start_address} and {end_address}")
        
        # Try to suggest alternatives
        start_component = None
        end_component = None
        
        for i, component in enumerate(connected_components):
            if start_stop in component:
                start_component = i
            if end_stop in component:
                end_component = i
        
        if start_component is not None and end_component is not None:
            print(f"Start and end stops are in different components: {start_component} and {end_component}")
        
        # Find closest stops that might be in the same component
        print("Trying to find alternative stops...")
        
        # Find the largest component
        largest_component = max(connected_components, key=len)
        
        # Find closest stops in the largest component
        closest_start = None
        closest_end = None
        min_start_distance = float('inf')
        min_end_distance = float('inf')
        
        start_lat, start_lon = stops[start_stop]
        end_lat, end_lon = stops[end_stop]
        
        for stop_id in largest_component:
            stop_lat, stop_lon = stops[stop_id]
            
            # Distance to start
            start_distance = ((start_lat - stop_lat)**2 + (start_lon - stop_lon)**2) ** 0.5
            if start_distance < min_start_distance:
                min_start_distance = start_distance
                closest_start = stop_id
            
            # Distance to end
            end_distance = ((end_lat - stop_lat)**2 + (end_lon - stop_lon)**2) ** 0.5
            if end_distance < min_end_distance:
                min_end_distance = end_distance
                closest_end = stop_id
        
        if closest_start and closest_end:
            print(f"Closest connected stops:")
            start_name = stops_df[stops_df['stop_id'] == closest_start]['stop_name'].values[0]
            end_name = stops_df[stops_df['stop_id'] == closest_end]['stop_name'].values[0]
            print(f"  From: {start_name} (instead of {start_stop})")
            print(f"  To: {end_name} (instead of {end_stop})")
            
            # Try with these stops
            alternative_path, alternative_edge_types = alt_algorithm(G, closest_start, closest_end)
            
            if alternative_path:
                print(f"Alternative path found! You can try:")
                print(f"1. Walk from {start_address} to {start_name}")
                print(f"2. Take transit through {len(alternative_path)} stops")
                print(f"3. Walk from {end_name} to {end_address}")
else:
    print("Could not find nearby stops for the given addresses")