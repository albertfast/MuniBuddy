import os
import logging
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@localhost:5432/munibuddy_db")

# Create database connection
logger.debug("Connecting to database...")
engine = create_engine(DATABASE_URL)
connection = engine.connect()

# Create transit_edges table if it doesn't exist
logger.debug("Creating transit_edges table if it doesn't exist...")
create_table_sql = """
CREATE TABLE IF NOT EXISTS transit_edges (
    id SERIAL PRIMARY KEY,
    from_stop VARCHAR(255) NOT NULL,
    to_stop VARCHAR(255) NOT NULL,
    route_id VARCHAR(255),
    travel_time FLOAT NOT NULL,
    distance FLOAT,
    trip_id VARCHAR(255),
    CONSTRAINT unique_edge UNIQUE(from_stop, to_stop, route_id)
);
"""
connection.execute(text(create_table_sql))
connection.commit()

# Load GTFS data
logger.debug("Loading GTFS data...")
GTFS_DIR = os.path.join(os.path.dirname(__file__), "gtfs_data")
STOPS_FILE = os.path.join(GTFS_DIR, "stops.txt")
STOP_TIMES_FILE = os.path.join(GTFS_DIR, "stop_times.txt")
TRIPS_FILE = os.path.join(GTFS_DIR, "trips.txt")

stops_df = pd.read_csv(STOPS_FILE, dtype=str)
stop_times_df = pd.read_csv(STOP_TIMES_FILE, dtype=str)
trips_df = pd.read_csv(TRIPS_FILE, dtype=str)

# Convert coordinates to float
stops_df['stop_lat'] = stops_df['stop_lat'].astype(float)
stops_df['stop_lon'] = stops_df['stop_lon'].astype(float)

# Create a dictionary of stop coordinates for quick lookup
stops_dict = {}
for _, row in stops_df.iterrows():
    stops_dict[row['stop_id']] = (row['stop_lat'], row['stop_lon'])

# Process stop times to calculate travel times
logger.debug("Processing stop times and creating transit edges...")
edges = []
trip_groups = stop_times_df.groupby("trip_id")

for trip_id, trip_stops in trip_groups:
    # Get route_id for this trip
    route_info = trips_df[trips_df['trip_id'] == trip_id]
    if len(route_info) == 0:
        continue
    route_id = route_info.iloc[0]['route_id']
    
    # Sort by stop sequence
    trip_stops = trip_stops.sort_values("stop_sequence")
    
    # Connect consecutive stops
    for i in range(len(trip_stops) - 1):
        from_stop = trip_stops.iloc[i]['stop_id']
        to_stop = trip_stops.iloc[i + 1]['stop_id']
        
        # Calculate travel time (if available)
        try:
            departure = pd.to_datetime(trip_stops.iloc[i]['departure_time'])
            arrival = pd.to_datetime(trip_stops.iloc[i + 1]['arrival_time'])
            travel_time = (arrival - departure).total_seconds() / 60  # in minutes
        except:
            # If time format is problematic, estimate based on distance
            if from_stop in stops_dict and to_stop in stops_dict:
                from_lat, from_lon = stops_dict[from_stop]
                to_lat, to_lon = stops_dict[to_stop]
                # Simple Euclidean distance as estimate
                distance = ((from_lat - to_lat)**2 + (from_lon - to_lon)**2) ** 0.5
                travel_time = distance * 100  # rough estimate: 100 minutes per degree
            else:
                travel_time = 5  # default 5 minutes if we can't calculate
        
        # Calculate physical distance
        distance = None
        if from_stop in stops_dict and to_stop in stops_dict:
            from_lat, from_lon = stops_dict[from_stop]
            to_lat, to_lon = stops_dict[to_stop]
            distance = ((from_lat - to_lat)**2 + (from_lon - to_lon)**2) ** 0.5
        
        edges.append({
            'from_stop': from_stop,
            'to_stop': to_stop,
            'route_id': route_id,
            'travel_time': travel_time,
            'distance': distance,
            'trip_id': trip_id
        })

# Create DataFrame from collected edges
edges_df = pd.DataFrame(edges)

# Remove duplicates (keep shortest travel time)
edges_df = edges_df.sort_values('travel_time').drop_duplicates(
    subset=['from_stop', 'to_stop', 'route_id'], keep='first'
)

# Insert edges into database
logger.debug(f"Inserting {len(edges_df)} transit edges into database...")
try:
    # Truncate table first to avoid duplicates
    connection.execute(text("TRUNCATE transit_edges"))
    connection.commit()
    
    # Insert in batches for better performance
    batch_size = 1000
    for i in range(0, len(edges_df), batch_size):
        batch = edges_df.iloc[i:i+batch_size]
        
        for _, edge in batch.iterrows():
            insert_sql = """
            INSERT INTO transit_edges (from_stop, to_stop, route_id, travel_time, distance, trip_id)
            VALUES (:from_stop, :to_stop, :route_id, :travel_time, :distance, :trip_id)
            ON CONFLICT (from_stop, to_stop, route_id) DO UPDATE 
            SET travel_time = EXCLUDED.travel_time, 
                distance = EXCLUDED.distance,
                trip_id = EXCLUDED.trip_id
            """
            connection.execute(text(insert_sql), {
                'from_stop': edge['from_stop'],
                'to_stop': edge['to_stop'],
                'route_id': edge['route_id'],
                'travel_time': float(edge['travel_time']),
                'distance': float(edge['distance']) if edge['distance'] is not None else None,
                'trip_id': edge['trip_id']
            })
        
        connection.commit()
        logger.debug(f"Inserted batch {i//batch_size + 1}/{(len(edges_df)-1)//batch_size + 1}")

    # Count inserted rows
    count = connection.execute(text("SELECT COUNT(*) FROM transit_edges")).scalar()
    logger.debug(f"Successfully inserted {count} transit edges")
    
except Exception as e:
    logger.error(f"Error inserting transit edges: {e}")

finally:
    connection.close()

logger.debug("Transit edges table creation completed.")