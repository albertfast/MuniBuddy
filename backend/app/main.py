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
#rom app.services.gtfs_service import load_gtfs_data
from app.db.database import init_db, SessionLocal
# from app.router.bus import router as bus_router
from app.router.nearby_stops import router as nearby_stops_router
from app.router.nearby_bus_positions import router as nearby_bus_router
from app.router.stop_schedule import router as stop_schedule_router
from app.router.deploy import router as deploy_router
#from app.utils.json_cleaner import clean_api_response
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
#app.include_router(bus_router, prefix="/api/v1", tags=["Bus Routes"])
app.include_router(nearby_stops_router, prefix="/api/v1", tags=["Nearby Stops"])                    
app.include_router(nearby_bus_router, prefix="/api/v1", tags=["Nearby Bus Stops"])          
app.include_router(stop_schedule_router, prefix="/api/v1", tags=["Stop Schedules"])
app.include_router(deploy_router, prefix="/api/v1/deploy")                   
       
#app.include_router(route_router, prefix="/api/v1") 

# Optional legacy
# app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    init_db()
