import networkx as nx
import heapq
import pandas as pd
import os
from geopy.geocoders import Nominatim
from dotenv import load_dotenv

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

# Debug: Print current working directory
print(f"Current working directory: {os.getcwd()}")
print(f"GTFS directory path: {GTFS_DIR}")
print(f"GTFS directory exists: {os.path.exists(GTFS_DIR)}")

try:
    routes_df = pd.read_csv(ROUTES_FILE, dtype=str)
    stops_df = pd.read_csv(STOPS_FILE, dtype=str)
    stop_times_df = pd.read_csv(STOP_TIMES_FILE, dtype=str)
    trips_df = pd.read_csv(TRIPS_FILE, dtype=str)
    
    print(f"Loaded routes: {len(routes_df)}")
    print(f"Loaded stops: {len(stops_df)}")
    print(f"Loaded stop_times: {len(stop_times_df)}")
    print(f"Loaded trips: {len(trips_df)}")
except Exception as e:
    print(f"Error loading GTFS data: {e}")

# ** Durakları Lat-Lon ile Eşleştir **
stops = {}
for _, row in stops_df.iterrows():
    stops[row['stop_id']] = (float(row['stop_lat']), float(row['stop_lon']))

# ** Otobüs Hatlarına Göre Bağlantıları Kur **
G = nx.DiGraph()
for _, row in stop_times_df.iterrows():
    stop_id = row['stop_id']
    trip_id = row['trip_id']
    if stop_id in stops:
        lat, lon = stops[stop_id]
        G.add_node(stop_id, name=stops_df.loc[stops_df["stop_id"] == stop_id, "stop_name"].values[0], lat=lat, lon=lon)

# ** İlgili Hatları Bağlayalım **
trip_groups = stop_times_df.groupby("trip_id")
for _, trip in trip_groups:
    stop_sequence = trip.sort_values(by="stop_sequence")
    stop_list = stop_sequence["stop_id"].tolist()
    for i in range(len(stop_list) - 1):
        stop1, stop2 = stop_list[i], stop_list[i + 1]
        if stop1 in stops and stop2 in stops:
            lat1, lon1 = stops[stop1]
            lat2, lon2 = stops[stop2]
            distance = ((lat1 - lat2)**2 + (lon1 - lon2)**2) ** 0.5
            
            # Eğer edge yoksa ekleyelim
            if not G.has_edge(stop1, stop2):
                G.add_edge(stop1, stop2, weight=distance)

# Debug: place_12TH durakları bağlı mı?
print(f"Graph neighbors of place_12TH: {list(G.neighbors('place_12TH'))}")
print(f"Graph predecessors of place_12TH: {list(G.predecessors('place_12TH'))}")

# Debug: place_12TH hangi triplerde var?
place_12TH_trips = stop_times_df[stop_times_df["stop_id"] == "place_12TH"]["trip_id"].unique()
print(f"Trips that include place_12TH: {place_12TH_trips}")

for trip_id in place_12TH_trips:
    trip_stops = stop_times_df[stop_times_df["trip_id"] == trip_id].sort_values("stop_sequence")
    print(f"Trip {trip_id} stops: {trip_stops['stop_id'].tolist()}")

# ** Landmark noktaları **
landmarks = list(stops.keys())[:2]  # İlk iki durağı landmark yapıyoruz

# ** Landmark mesafelerini önceden hesaplayalım **
landmark_distances = {}
for landmark in landmarks:
    distances = nx.single_source_dijkstra_path_length(G, landmark, weight='weight')
    landmark_distances[landmark] = distances

# ** ALT Algoritması (A* + Landmark) **
def alt_algorithm(graph, start, end):
    """ Landmark destekli A* algoritması """
    def heuristic(node):
        return max(
            abs(landmark_distances[lm].get(node, float('inf')) - landmark_distances[lm].get(end, float('inf')))
            for lm in landmarks
        )
    
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {node: float('inf') for node in graph.nodes}
    g_score[start] = 0
    f_score = {node: float('inf') for node in graph.nodes}
    f_score[start] = heuristic(start)
    
    while open_set:
        _, current = heapq.heappop(open_set)
        
        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            return path[::-1]
        
        for neighbor in graph.neighbors(current):
            tentative_g_score = g_score[current] + graph[current][neighbor]['weight']
            if tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = g_score[neighbor] + heuristic(neighbor)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
    
    return None  # Yol bulunamazsa

# ** Rastgele bir başlangıç ve bitiş durağı seç **
start, end = list(stops.keys())[0], list(stops.keys())[-1]

# ** ALT Algoritmasını çalıştır **
shortest_path = alt_algorithm(G, start, end)
print(f"Başlangıç durağı: {start}, Bitiş durağı: {end}")
print(f"En kısa yol: {[stops[i] for i in shortest_path]}")

# ** Örnek test senaryosu: Golden Gate Park -> Union Square **
start_location = "Golden Gate Park, San Francisco"
end_location = "Union Square, San Francisco"

print(f"Finding nearest stop for: {start_location}")
start_geo = geolocator.geocode(start_location)
start_latlon = (start_geo.latitude, start_geo.longitude)
nearest_start = min(stops.keys(), key=lambda s: ((stops[s][0] - start_latlon[0])**2 + (stops[s][1] - start_latlon[1])**2) ** 0.5)
print(f"Geocoded location: {start_geo.latitude}, {start_geo.longitude}")
print(f"Nearest stop: {stops_df.loc[stops_df['stop_id'] == nearest_start, 'stop_name'].values[0]} (Stop ID: {nearest_start})")

print(f"Finding nearest stop for: {end_location}")
end_geo = geolocator.geocode(end_location)
end_latlon = (end_geo.latitude, end_geo.longitude)
nearest_end = min(stops.keys(), key=lambda s: ((stops[s][0] - end_latlon[0])**2 + (stops[s][1] - end_latlon[1])**2) ** 0.5)
print(f"Geocoded location: {end_geo.latitude}, {end_geo.longitude}")
print(f"Nearest stop: {stops_df.loc[stops_df['stop_id'] == nearest_end, 'stop_name'].values[0]} (Stop ID: {nearest_end})")

print(f"Finding path from {nearest_start} to {nearest_end}...")
shortest_path = alt_algorithm(G, nearest_start, nearest_end)

if shortest_path:
    print(f"Path found with {len(shortest_path)} stops.")
    print(f"Başlangıç: {start_location} (Stop ID: {nearest_start})")
    print(f"Bitiş: {end_location} (Stop ID: {nearest_end})")
    print("En kısa yol:")
    
    transit_segments = 0
    walking_segments = 0
    
    for i, stop in enumerate(shortest_path):
        stop_name = stops_df.loc[stops_df["stop_id"] == stop, "stop_name"].values[0]
        if i == 0:
            print(f"  - 🚶 Walking to {stop_name}")
            walking_segments += 1
        elif i == len(shortest_path) - 1:
            print(f"  - 🚶 Walking to {stop_name}")
            walking_segments += 1
        else:
            print(f"  - [🚌 Transit] {stop_name}")
            transit_segments += 1
    
    total_distance = sum(G[shortest_path[i]][shortest_path[i + 1]]['weight'] for i in range(len(shortest_path) - 1))
    print(f"Toplam mesafe: {total_distance:.2f} ml")
    print(f"Transit segments: {transit_segments}")
    print(f"Walking segments: {walking_segments}")
else:
    print("❌ No path found!")
