from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.bus_route import BusRoute
from app.utils.xml_parser import xml_to_json
from app.config import settings
import requests
import os
import pandas as pd
from redis import Redis
import json
from typing import Optional
from math import radians, sin, cos, sqrt, atan2
import logging
from app.services.bus_service import BusService

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)

API_KEY = settings.API_KEY
AGENCY_ID = settings.AGENCY_ID
BASE_API_URL = "http://api.511.org/transit"

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using Haversine formula."""
    R = 3959.87433  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c

    return distance

@router.get("/nearby-stops")
async def get_nearby_stops(
    lat: float = Query(..., description="Latitude of the location"),
    lon: float = Query(..., description="Longitude of the location"),
    radius_miles: float = Query(0.5, description="Search radius in miles"),
    db: Session = Depends(get_db)
):
    """Get nearby bus stops within the specified radius."""
    try:
        bus_service = BusService()
        return await bus_service.find_nearby_stops(lat, lon, radius_miles)
    except Exception as e:
        logger.error(f"Error getting nearby stops: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/routes")
def get_routes(db: Session = Depends(get_db)):
    """Fetch all bus routes from the database."""
    return db.query(BusRoute).all()

@router.get("/bus-positions")
def get_bus_positions(bus_number: str, agency: str):
    """Returns real-time bus positions."""
    return {"bus_number": bus_number, "agency": agency}


@router.get("/get-route-details")
def get_route_details(db: Session = Depends(get_db), route_short_name: str = Query(..., description="Bus route short name")):
    """Fetch route details from GTFS or 511 API if not found."""
    
    route = db.query(BusRoute).filter(BusRoute.route_id == route_short_name).first()
    if route:
        return {
            "route_id": route.route_id,
            "route_name": route.route_name,
            "origin": route.origin,
            "destination": route.destination
        }

    # If not found in GTFS, fetch from 511 API
    api_url = f"http://api.511.org/transit/RouteDetails?api_key={API_KEY}&agency={AGENCY_ID}&route_id={route_short_name}&format=json"
    response = requests.get(api_url)
    
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Route not found in GTFS or 511 API")

    return response.json()


@router.get("/bus-positions")
def get_bus_positions(bus_number: str, agency: str):
    """Get real-time bus positions from 511 API."""
    
    api_url = f"{BASE_API_URL}/VehicleMonitoring?api_key={API_KEY}&agency={agency}"
    response = requests.get(api_url)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="511 API request failed.")

    data = xml_to_json(response.text)  # Convert XML to JSON
    vehicles = data.get("Siri", {}).get("ServiceDelivery", {}).get("VehicleMonitoringDelivery", {}).get("VehicleActivity", [])

    if not vehicles:
        return {"message": "No live bus data available"}

    buses = []
    for vehicle in vehicles:
        journey = vehicle.get("MonitoredVehicleJourney", {})
        if journey.get("LineRef") == bus_number:
            buses.append({
                "bus_number": journey.get("LineRef"),
                "current_stop": journey.get("MonitoredCall", {}).get("StopPointName", "Unknown"),
                "latitude": journey.get("VehicleLocation", {}).get("Latitude"),
                "longitude": journey.get("VehicleLocation", {}).get("Longitude"),
                "expected_arrival": journey.get("MonitoredCall", {}).get("ExpectedArrivalTime"),
            })

    if not buses:
        return {"message": "Bus not found in live data"}

    return {"bus_positions": buses}

@router.get("/cached-bus-positions")
def get_cached_bus_positions(bus_number: str, agency: str):
    """Fetches bus positions from cache if available, otherwise fetch from API."""
    
    cache_key = f"bus:{bus_number}:{agency}"
    cached_data = redis.get(cache_key)
    
    if cached_data:
        return json.loads(cached_data)
    
    # If not in cache, get live data
    bus_data = get_bus_positions(bus_number, agency) 
    redis.setex(cache_key, 300, json.dumps(bus_data))
    
    return bus_data

@router.get("/stop-schedule/{stop_id}")
async def get_stop_schedule(stop_id: str, db: Session = Depends(get_db)):
    """Get real-time bus schedule for a specific stop."""
    try:
        bus_service = BusService()
        logger.debug(f"Fetching stop schedule from: http://api.511.org/transit/StopMonitoring?api_key={bus_service.api_key}&agency=SF&stopId={stop_id}&format=json")
        schedule = await bus_service.get_stop_schedule(stop_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return schedule
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing transit service response")
    except Exception as e:
        logger.error(f"Error getting stop schedule: {str(e)}")
        raise HTTPException(status_code=503, detail="Error connecting to transit service")