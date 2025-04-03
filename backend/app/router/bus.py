from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from redis import Redis
from typing import Optional
from math import radians, sin, cos, sqrt, atan2
import logging
import requests
import json

from app.db.database import get_db
from app.services.bus_service import BusService
from app.models.bus_route import BusRoute
from app.utils.xml_parser import xml_to_json
from app.config import settings

routes_df, trips_df, stops_df, stop_times_df, calendar_df = settings.gtfs_data

# Initialize
logger = logging.getLogger(__name__)
router = APIRouter()
bus_service = BusService()
redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)

API_KEY = settings.API_KEY
AGENCY_ID = settings.AGENCY_ID
BASE_API_URL = "http://api.511.org/transit"

# Distance helper
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3959.87433
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    a = sin((lat2 - lat1)/2)**2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1)/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

# ------------------- API ROUTES -------------------

@router.get("/nearby-stops")
async def get_nearby_stops(
    lat: float = Query(..., description="Latitude of the location"),
    lon: float = Query(..., description="Longitude of the location"),
    radius_miles: float = Query(0.5, description="Search radius in miles"),
    db: Session = Depends(get_db)
):
    try:
        return await bus_service.find_nearby_stops(lat, lon, radius_miles)
    except Exception as e:
        logger.error(f"Error getting nearby stops: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nearby-stops-with-schedule")
async def get_nearby_stops_with_schedule(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_miles: float = 0.15
):
    try:
        nearby_stops = await bus_service.find_nearby_stops(lat, lon, radius_miles)
        for stop in nearby_stops:
            stop['schedule'] = await bus_service.get_stop_schedule(stop['stop_id'])
        return nearby_stops
    except Exception as e:
        logger.exception("Error fetching nearby stops with schedules")
        raise HTTPException(status_code=500, detail="Failed to load stop schedules")

@router.get("/routes")
def get_routes(db: Session = Depends(get_db)):
    return db.query(BusRoute).all()

@router.get("/get-route-details")
def get_route_details(
    db: Session = Depends(get_db), 
    route_short_name: str = Query(..., description="Bus route short name")
):
    route = db.query(BusRoute).filter(BusRoute.route_short_name == route_short_name).first()

    if route:
        return {
            "route_id": route.route_id,
            "route_name": route.route_name,
            "origin": route.origin,
            "destination": route.destination
        }

    api_url = f"{BASE_API_URL}/RouteDetails"
    params = {
        "api_key": API_KEY,
        "agency": AGENCY_ID,
        "route_id": route_short_name,
        "format": "json"
    }

    try:
        response = requests.get(api_url, params=params, timeout=10)
        if response.status_code != 200 or not response.content:
            raise HTTPException(status_code=404, detail="Route not found in GTFS or 511 API")
        return response.json()
    except requests.RequestException as e:
        logger.error(f"511 API request error: {e}")
        raise HTTPException(status_code=503, detail="511 API unreachable")

@router.get("/bus-positions")
def get_bus_positions(bus_number: str, agency: str):
    try:
        api_url = f"{BASE_API_URL}/VehicleMonitoring?api_key={API_KEY}&agency={agency}"
        response = requests.get(api_url, timeout=10)

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="511 API request failed.")

        data = xml_to_json(response.text)
        vehicles = data.get("Siri", {}).get("ServiceDelivery", {}).get("VehicleMonitoringDelivery", {}).get("VehicleActivity", [])

        buses = []
        for vehicle in vehicles:
            journey = vehicle.get("MonitoredVehicleJourney", {})
            line_ref = journey.get("LineRef", "")
            if bus_number in line_ref:
                buses.append({
                    "bus_number": line_ref,
                    "current_stop": journey.get("MonitoredCall", {}).get("StopPointName", "Unknown"),
                    "latitude": journey.get("VehicleLocation", {}).get("Latitude"),
                    "longitude": journey.get("VehicleLocation", {}).get("Longitude"),
                    "expected_arrival": journey.get("MonitoredCall", {}).get("ExpectedArrivalTime"),
                })

        return {"bus_positions": buses} if buses else {"message": "Bus not found in live data"}
    
    except Exception as e:
        logger.exception("Error fetching live bus positions")
        raise HTTPException(status_code=500, detail="Failed to fetch live data")

@router.get("/cached-bus-positions")
def get_cached_bus_positions(bus_number: str, agency: str):
    cache_key = f"bus:{bus_number}:{agency}"
    cached_data = redis.get(cache_key)

    if cached_data:
        try:
            return json.loads(cached_data)
        except json.JSONDecodeError:
            logger.warning(f"Invalid cached JSON for {cache_key}")

    try:
        live_data = bus_service.get_live_bus_positions(bus_number, agency)
        redis.setex(cache_key, 300, json.dumps(live_data))
        return live_data
    except Exception as e:
        logger.exception("Error in get_cached_bus_positions")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stop-schedule/{stop_id}")
async def get_stop_schedule(stop_id: str, db: Session = Depends(get_db)):
    try:
        schedule = await bus_service.get_stop_schedule(stop_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return schedule
    except Exception as e:
        logger.exception(f"Failed to get stop schedule for stop_id={stop_id}")
        raise HTTPException(status_code=503, detail="Could not connect to transit service")