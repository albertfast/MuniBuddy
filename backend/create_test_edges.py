import os
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@localhost:5432/munibuddy_db")

# Create database connection
logger.info("Connecting to database...")
engine = create_engine(DATABASE_URL)
connection = engine.connect()

try:
    # Create transit_edges table if it doesn't exist
    logger.info("Creating transit_edges table...")
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
    logger.info("Table created successfully")

    # Get a sample of stops from the database to use for edges
    logger.info("Getting sample stops...")
    stops = connection.execute(text("""
        SELECT stop_id, stop_lat, stop_lon 
        FROM stops 
        LIMIT 100
    """)).fetchall()

    if len(stops) < 20:
        logger.error("Not enough stops in the database to create test edges")
        exit(1)

    logger.info(f"Found {len(stops)} stops")

    # Create a simple connected network from these stops
    logger.info("Creating test transit edges...")
    connection.execute(text("TRUNCATE transit_edges"))
    connection.commit()
    
    # Connect stops in sequence
    for i in range(len(stops) - 1):
        from_stop = stops[i][0]  # stop_id
        to_stop = stops[i + 1][0]  # stop_id
        from_lat, from_lon = stops[i][1], stops[i][2]
        to_lat, to_lon = stops[i + 1][1], stops[i + 1][2]
        
        # Calculate simple distance
        distance = ((from_lat - to_lat)**2 + (from_lon - to_lon)**2) ** 0.5
        travel_time = distance * 1000  # Simple conversion to minutes
        
        # Insert edge in both directions
        for direction in [(from_stop, to_stop), (to_stop, from_stop)]:
            connection.execute(text("""
                INSERT INTO transit_edges 
                (from_stop, to_stop, route_id, travel_time, distance, trip_id)
                VALUES (:from_stop, :to_stop, '1', :travel_time, :distance, '1')
                ON CONFLICT (from_stop, to_stop, route_id) DO NOTHING
            """), {
                'from_stop': direction[0],
                'to_stop': direction[1],
                'travel_time': float(travel_time),
                'distance': float(distance)
            })
    
    # Add some cross-connections to make the network more interesting
    for i in range(0, len(stops) - 10, 5):
        from_stop = stops[i][0]
        to_stop = stops[i + 10][0]
        from_lat, from_lon = stops[i][1], stops[i][2]
        to_lat, to_lon = stops[i + 10][1], stops[i + 10][2]
        
        distance = ((from_lat - to_lat)**2 + (from_lon - to_lon)**2) ** 0.5
        travel_time = distance * 1000
        
        # Insert edge in both directions
        for direction in [(from_stop, to_stop), (to_stop, from_stop)]:
            connection.execute(text("""
                INSERT INTO transit_edges 
                (from_stop, to_stop, route_id, travel_time, distance, trip_id)
                VALUES (:from_stop, :to_stop, '2', :travel_time, :distance, '2')
                ON CONFLICT (from_stop, to_stop, route_id) DO NOTHING
            """), {
                'from_stop': direction[0],
                'to_stop': direction[1],
                'travel_time': float(travel_time),
                'distance': float(distance)
            })
    
    connection.commit()
    
    # Verify edges were created
    edge_count = connection.execute(text("SELECT COUNT(*) FROM transit_edges")).scalar()
    logger.info(f"Successfully created {edge_count} test edges")
    
except Exception as e:
    logger.error(f"Error: {e}")
    connection.rollback()
finally:
    connection.close()
    logger.info("Done")