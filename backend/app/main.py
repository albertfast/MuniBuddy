# Standard library imports
import os
import sys
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Third-party imports
import requests
import redis
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

# Local application imports
from app.config import settings
from app.router.bus import router as bus_router
from app.router.nearby_stops import router as nearby_stops_router
from app.router.stop_schedule import router as stop_schedule_router
from app.db.database import engine, Base, init_db
from app.api import api_router
from app.utils.json_cleaner import clean_api_response

# Constants
API_VERSION = "1.0.0"

# Initialize database
init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)
router = APIRouter()

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify allowed domains for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Application configuration
app.config = {
    "api_key": settings.API_KEY,
    "agency_id": settings.AGENCY_ID,
    "database_url": settings.SQLALCHEMY_DATABASE_URI
}

# Router includes
app.include_router(bus_router)
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(nearby_stops_router)
app.include_router(stop_schedule_router)

# Environment variables
API_KEY = settings.API_KEY
AGENCY_ID = settings.AGENCY_ID
REDIS_HOST = settings.REDIS_HOST
REDIS_PORT = settings.REDIS_PORT

# Redis connection with error handling
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True
    )
except redis.ConnectionError as e:
    print(f"Failed to connect to Redis: {e}")
    redis_client = None

@app.get("/")
async def root():
    return {"message": "Welcome to MuniBuddy API!"}

@router.get("/cached-bus-positions")
def get_cached_bus_positions(bus_number: str, agency: str):
    """
    Fetches bus positions from cache if available, otherwise fetch from API.
    """
    if not redis_client:
        return {"error": "Redis connection not available"}

    cache_key = f"bus:{bus_number}:{agency}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data:
        return clean_api_response(cached_data)
    
    # Fetch from 511 API
    api_url = f"http://api.511.org/transit/VehicleMonitoring?api_key={API_KEY}&agency={agency}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
    except requests.RequestException as e:
        return {
            "error": "511 API request failed",
            "details": str(e)
        }

    # Clean the API response
    data = clean_api_response(response.text)
    
    if "error" in data:
        return data

    vehicles = data.get("Siri", {}).get("ServiceDelivery", {}).get("VehicleMonitoringDelivery", {}).get("VehicleActivity", [])

    if not vehicles:
        return {
            "message": "No live bus data available",
            "api_response": data
        }

    buses = []
    for vehicle in vehicles:
        journey = vehicle.get("MonitoredVehicleJourney", {})
        if journey.get("LineRef") == bus_number:
            bus_data = {
                "bus_number": journey.get("LineRef"),
                "current_stop": journey.get("MonitoredCall", {}).get("StopPointName", "Unknown"),
                "latitude": journey.get("VehicleLocation", {}).get("Latitude"),
                "longitude": journey.get("VehicleLocation", {}).get("Longitude"),
                "expected_arrival": journey.get("MonitoredCall", {}).get("ExpectedArrivalTime"),
            }
            # Clean each bus data individually
            buses.append(clean_api_response(json.dumps(bus_data)))

    if not buses:
        return {
            "message": "Bus not found in live data",
            "api_response": data
        }

    # Cache the cleaned results
    if redis_client:
        redis_client.setex(cache_key, 300, json.dumps(buses))

    return {"bus_positions": buses}