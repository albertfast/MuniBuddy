import os
import sys
import json

# Add parent directory to path for local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Third-party imports
import requests
import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Local imports
from app.config import settings
from app.services.gtfs_service import load_gtfs_data
from app.db.database import init_db
from app.api.routes import transit
from app.route_finder import router as route_router
from app.router.bus import router as bus_router
from app.router.nearby_stops import router as nearby_stops_router
from app.router.stop_schedule import router as stop_schedule_router
from app.router.deploy import router as deploy_router
from app.api.routes.transit import *  # Optional legacy
from app.utils.json_cleaner import clean_api_response
from app.services.bus_service import BusService

# FastAPI App Initialization
app = FastAPI(
    title="MuniBuddy - SF Transit Finder",
    description="Real-time SF Muni data using GTFS + 511 API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://munibuddy.live", "http://165.232.140.152"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.gtfs_data = load_gtfs_data(settings.MUNI_GTFS_PATH)

# Redis Setup
try:
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True
    )
except redis.ConnectionError as e:
    print(f"Redis connection failed: {e}")
    redis_client = None

# Root Route
@app.get("/")
async def root():
    return {"message": "Welcome to MuniBuddy API!"}

# Extra demo/test endpoint
@app.get("/api/nearby-stops-with-schedule")
async def get_nearby_stops_with_schedule(lat: float, lon: float):
    service = BusService()
    stops = await service.find_nearby_stops(lat, lon)
    results = []

    for stop in stops:
        schedule = await service.get_stop_schedule(stop['stop_id'])
        stop['schedule'] = schedule
        results.append(stop)

    return results

# Routers organized clearly:
app.include_router(bus_router, prefix="/api/v1")                     # /api/v1/bus/...
app.include_router(nearby_stops_router, prefix="/api/v1")           # /api/v1/nearby-stops
app.include_router(stop_schedule_router, prefix="/api/v1")          # /api/v1/stop-schedule
app.include_router(deploy_router, prefix="/api/v1/deploy")                    # /api/deploy

app.include_router(transit.router, prefix="/api/transit")           # /api/transit/...
app.include_router(route_router, prefix="/api/v1")            # /api/optimized-route

# Optional legacy
# app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    init_db()
