import os
import sys
import logging
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@localhost:5432/munibuddy_db")
API_KEY = os.getenv("API_KEY")

logger.debug("Starting route finder debug test...")

# Create database connection
try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    logger.debug("Database connection established")
except Exception as e:
    logger.error(f"Failed to connect to database: {e}")
    sys.exit(1)

# Import route finder functions
try:
    from route_finder2 import find_nearest_stop, get_live_bus_positions, a_star_search
    logger.debug("Successfully imported route finder functions")
except ImportError as e:
    logger.error(f"Failed to import route finder functions: {e}")
    sys.exit(1)

# Test database tables
try:
    logger.debug("Testing database tables...")
    # Test stops table
    result = db.execute(text("SELECT COUNT(*) FROM stops")).scalar()
    logger.debug(f"Found {result} stops in database")
    
    # Test transit_edges table
    result = db.execute(text("SELECT COUNT(*) FROM transit_edges")).scalar()
    logger.debug(f"Found {result} transit edges in database")
except Exception as e:
    logger.error(f"Database table error: {e}")
    logger.debug("Make sure you've created the necessary tables with proper permissions")
    sys.exit(1)

# Test coordinates
start_locations = [
    {"name": "San Francisco Zoo", "lat": 37.7329, "lon": -122.5024},
    {"name": "Golden Gate Park", "lat": 37.7694, "lon": -122.4862}
]

end_locations = [
    {"name": "Fisherman's Wharf", "lat": 37.8081, "lon": -122.4166},
    {"name": "Union Square", "lat": 37.7881, "lon": -122.4075}
]

# Test find_nearest_stop function
for loc in start_locations + end_locations:
    logger.debug(f"Finding nearest stop for {loc['name']}...")
    start_time = time.time()
    try:
        stop = find_nearest_stop(loc['lat'], loc['lon'], db)
        if stop:
            logger.debug(f"✅ Found nearest stop: {stop['stop_name']} ({stop['stop_id']})")
            logger.debug(f"   Coordinates: {stop['stop_lat']}, {stop['stop_lon']}")
        else:
            logger.warning(f"⚠️ No stop found near {loc['name']}")
        logger.debug(f"   (Took {time.time() - start_time:.2f} seconds)")
    except Exception as e:
        logger.error(f"❌ Error finding nearest stop for {loc['name']}: {e}")

# Test live bus positions
logger.debug("Testing live bus positions API...")
try:
    start_time = time.time()
    live_buses = get_live_bus_positions()
    if live_buses:
        logger.debug(f"✅ Received {len(live_buses)} live bus positions")
    else:
        logger.warning("⚠️ No live bus positions received")
    logger.debug(f"   (Took {time.time() - start_time:.2f} seconds)")
except Exception as e:
    logger.error(f"❌ Error getting live bus positions: {e}")

# Test full route finding (pick one start and one end)
start = start_locations[0]
end = end_locations[0]

logger.debug(f"Testing route finding from {start['name']} to {end['name']}...")
try:
    start_time = time.time()
    
    # Find nearest stops
    start_stop = find_nearest_stop(start['lat'], start['lon'], db)
    end_stop = find_nearest_stop(end['lat'], end['lon'], db)
    
    if start_stop and end_stop:
        logger.debug(f"Found stops: {start_stop['stop_name']} to {end_stop['stop_name']}")
        
        # Get live bus data
        live_buses = get_live_bus_positions() or []
        
        # Find route
        logger.debug("Searching for optimal route...")
        route = a_star_search(start_stop, end_stop, live_buses, db)
        
        if route:
            # Get stop names for display
            stop_details = []
            for stop_id in route:
                result = db.execute(text("SELECT stop_name FROM stops WHERE stop_id = :stop_id"), 
                                  {"stop_id": stop_id}).fetchone()
                stop_name = result["stop_name"] if result else stop_id
                stop_details.append(stop_name)
            
            logger.debug("✅ Route found:")
            logger.debug(f"   From: {start_stop['stop_name']} ({start_stop['stop_id']})")
            logger.debug(f"   To: {end_stop['stop_name']} ({end_stop['stop_id']})")
            logger.debug(f"   Stops: {len(route)}")
            
            for i, stop in enumerate(stop_details):
                logger.debug(f"   {i+1}. {stop}")
        else:
            logger.warning(f"⚠️ No route found between {start_stop['stop_name']} and {end_stop['stop_name']}")
    else:
        logger.warning("⚠️ Could not find start or end stops")
    
    logger.debug(f"Route finding completed in {time.time() - start_time:.2f} seconds")
except Exception as e:
    logger.error(f"❌ Error in route finding: {e}")

logger.debug("Debug test completed")