from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.bus_service import BusService
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
bus_service = BusService()

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

@router.get("/nearby-stops-with-schedule")
async def get_nearby_stops_with_schedule(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_miles: float = 0.15
):
    nearby_stops = await bus_service.find_nearby_stops(lat, lon, radius_miles)
    results = []

    for stop in nearby_stops:
        schedule = await bus_service.get_stop_schedule(stop['stop_id'])

        # frontend için gerekli alanlar
        stop['schedule'] = schedule
        stop['stop_lat'] = stop.get('stop_lat')
        stop['stop_lon'] = stop.get('stop_lon')

        results.append(stop)

    return results

@router.get("/routes")
def get_routes(db: Session = Depends(get_db)):
    """Fetch all bus routes from the database."""
    return db.query(BusRoute).all()

@router.get("/get-route-details")
def get_route_details(
    db: Session = Depends(get_db), 
    route_short_name: str = Query(..., description="Bus route short name")
):
    """
    Fetch route details from GTFS database, or fallback to 511 API if not found.
    """

    logger.info(f"Searching route details for: {route_short_name}")

    # Try GTFS database
    route = db.query(BusRoute).filter(
        (BusRoute.route_id == route_short_name) | 
        (BusRoute.route_short_name == route_short_name)
    ).first()

    if route:
        logger.debug(f"Route found in GTFS: {route.route_id}")
        return {
            "route_id": route.route_id,
            "route_name": route.route_name,
            "origin": route.origin,
            "destination": route.destination
        }

    # Fallback to 511 API
    logger.info(f"Route not found in GTFS. Fetching from 511 API: {route_short_name}")
    
    api_url = f"http://api.511.org/transit/RouteDetails"
    params = {
        "api_key": API_KEY,
        "agency": AGENCY_ID,
        "route_id": route_short_name,
        "format": "json"
    }

    try:
        response = requests.get(api_url, params=params, timeout=10)

        if response.status_code != 200 or not response.content:
            logger.warning(f"511 API failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=404, detail="Route not found in GTFS or 511 API")

        return response.json()

    except requests.RequestException as e:
        logger.error(f"511 API request error: {e}")
        raise HTTPException(status_code=503, detail="Failed to fetch from 511 API")

@router.get("/bus-positions")
def get_bus_positions(bus_number: str, agency: str):
    """Get real-time bus positions from 511 API."""
    try:
        api_url = f"{BASE_API_URL}/VehicleMonitoring?api_key={API_KEY}&agency={agency}"
        response = requests.get(api_url, timeout=10)

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="511 API request failed.")

        data = xml_to_json(response.text)  # Convert XML to JSON

        vehicles = data.get("Siri", {}).get("ServiceDelivery", {}).get("VehicleMonitoringDelivery", {}).get("VehicleActivity", [])

        if not vehicles:
            return {"message": "No live bus data available"}

        buses = []
        for vehicle in vehicles:
            journey = vehicle.get("MonitoredVehicleJourney", {})
            line_ref = journey.get("LineRef", "")

            if bus_number in line_ref:  # More flexible matching
                buses.append({
                    "bus_number": line_ref,
                    "current_stop": journey.get("MonitoredCall", {}).get("StopPointName", "Unknown"),
                    "latitude": journey.get("VehicleLocation", {}).get("Latitude"),
                    "longitude": journey.get("VehicleLocation", {}).get("Longitude"),
                    "expected_arrival": journey.get("MonitoredCall", {}).get("ExpectedArrivalTime"),
                })

        if not buses:
            return {"message": "Bus not found in live data"}

        return {"bus_positions": buses}

    except Exception as e:
        logger.exception("Error in get_bus_positions")
        raise HTTPException(status_code=500, detail="Failed to fetch real-time bus positions")


@router.get("/cached-bus-positions")
def get_cached_bus_positions(bus_number: str, agency: str):
    """Fetch bus positions from Redis cache or fallback to live API."""
    try:
        cache_key = f"bus:{bus_number}:{agency}"
        cached_data = redis.get(cache_key)

        if cached_data:
            try:
                return json.loads(cached_data)
            except json.JSONDecodeError:
                logger.warning(f"Invalid cached JSON for {cache_key}, ignoring.")

        # Fallback to API
        bus_data = get_bus_positions(bus_number, agency)

        # If the data is valid and has positions, cache it
        if isinstance(bus_data, dict) and "bus_positions" in bus_data:
            redis.setex(cache_key, 300, json.dumps(bus_data))

        return bus_data

    except Exception as e:
        logger.exception("Error in get_cached_bus_positions")
        raise HTTPException(status_code=500, detail="Failed to fetch cached bus data")


@router.get("/stop-schedule/{stop_id}")
async def get_stop_schedule(stop_id: str, db: Session = Depends(get_db)):
    """Get real-time bus schedule for a specific stop from 511 API."""
    try:
        bus_service = BusService()
        logger.debug(f"Fetching stop schedule for stop_id={stop_id}")
        schedule = await bus_service.get_stop_schedule(stop_id)

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        return schedule

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error decoding schedule data")

    except Exception as e:
        logger.exception("Unhandled error in stop schedule")
        raise HTTPException(status_code=503, detail="Could not connect to transit service")
