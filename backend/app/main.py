import os
import sys
import json
import logging

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
from app.db.database import init_db, SessionLocal
from app.api.routes import transit
from app.route_finder import router as route_router
from app.router.bus import router as bus_router
from app.router.nearby_stops import router as nearby_stops_router
from app.router.stop_schedule import router as stop_schedule_router
from app.router.deploy import router as deploy_router
from app.api.routes.transit import *  # Optional legacy
from app.utils.json_cleaner import clean_api_response
from app.services.bus_service import BusService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

db = SessionLocal()
bus_service = BusService(db=db)

# FastAPI App Initialization
app = FastAPI(
    title="MuniBuddy API",
    description="Transit information and routing for SF Bay Area",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

routes_df, trips_df, stops_df, stop_times_df, calendar_df = settings.get_gtfs_data("muni")

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

# Health Check Route
@app.get("/health")
def health_check():
    return {"status": "ok"}

# Routers organized clearly:
app.include_router(bus_router, prefix="/api/v1", tags=["Bus Routes"])                     # /api/v1/bus/...
app.include_router(nearby_stops_router, prefix="/api/v1", tags=["Nearby Stops"])           # /api/v1/nearby-stops
app.include_router(stop_schedule_router, prefix="/api/v1", tags=["Stop Schedules"])          # /api/v1/stop-schedule
app.include_router(deploy_router, prefix="/api/v1/deploy")                    # /api/deploy

app.include_router(transit.router, prefix="/api/transit")           # /api/transit/...
app.include_router(route_router, prefix="/api/v1")            # /api/optimized-route

# Optional legacy
# app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    init_db()
    # import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000)
