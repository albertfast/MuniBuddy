import os
import sys
import json
import logging
import requests
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from redis import Redis
from app.db.database import get_db
from app.models.bus_route import BusRoute
from app.utils.xml_parser import xml_to_json
from app.config import settings
from app.core.singleton import bus_service

router = APIRouter()
logger = logging.getLogger(__name__)
redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)

API_KEY = settings.API_KEY
AGENCY_ID = settings.AGENCY_ID
BASE_API_URL = "http://api.511.org/transit"

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3959.87433  # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    a = sin((lat2 - lat1)/2)**2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1)/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


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


@router.get("/cached-bus-positions")
async def get_cached_bus_positions(bus_number: str, agency: str):
    """
    Get cached bus position data with fallback to live data.
    Uses Redis cache with 5 minute expiration.
    """
    cache_key = f"bus:positions:{agency}:{bus_number}"
    cached_data = redis.get(cache_key)

    if cached_data:
        try:
            logger.info(f"Cache hit for {cache_key}")
            return json.loads(cached_data)
        except json.JSONDecodeError:
            logger.warning(f"Invalid cached JSON for {cache_key}")
    
    logger.info(f"Cache miss for {cache_key} - fetching live data")
    
    try:
        buses = await bus_service.get_live_bus_positions_async(agency, bus_number)
        bus_positions = []

        for bus in buses:
            bus_positions.append({
                "bus_number": bus.get("route", ""),
                "current_stop": bus.get("next_stop", {}).get("name", "Unknown"),
                "latitude": bus.get("lat"),
                "longitude": bus.get("lng"),
                "expected_arrival": bus.get("arrival_time", ""),
                "direction": bus.get("direction", ""),
                "destination": bus.get("destination", "")
            })

        result = {"bus_positions": bus_positions}
        
        if bus_positions:
            redis.setex(cache_key, 300, json.dumps(result))
            logger.info(f"Cached {len(bus_positions)} positions for {cache_key}")
        else:
            redis.setex(cache_key, 60, json.dumps({"message": "No buses found"}))
        
        return result if bus_positions else {"message": "No buses found"}

    except Exception as e:
        logger.exception(f"Error in get_cached_bus_positions for {bus_number}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch bus positions: {str(e)}"
        )


@router.get("/bus-positions")
async def get_bus_positions(bus_number: str, agency: str):
    """
    Get real-time position information for buses of a specific route.
    """
    try:
        buses = await bus_service.get_live_bus_positions_async(agency, bus_number)
        if not buses:
            return {"message": "No live bus data available"}

        result = {
            "bus_positions": [
                {
                    "bus_number": bus.get("route", ""),
                    "current_stop": bus.get("next_stop", {}).get("name", "Unknown"),
                    "latitude": bus.get("lat"),
                    "longitude": bus.get("lng"),
                    "expected_arrival": bus.get("arrival_time"),
                    "direction": bus.get("direction", ""),
                    "destination": bus.get("destination", "")
                }
                for bus in buses
            ]
        }

        return result
    except Exception as e:
        logger.exception(f"Error fetching live bus positions: {e}")
        raise HTTPException(status_code=500, detail="Error fetching live bus positions")


@router.get("/api/stop-schedule/{stop_id}")
async def get_stop_schedule(stop_id: str):
    try:
        schedule = await bus_service.get_stop_schedule(stop_id)
        return schedule
    except Exception as e:
        logger.exception(f"Error getting stop schedule for {stop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/nearby-stops")
async def get_nearby_stops(
    lat: float,
    lon: float,
    radius_miles: float = 0.15
):
    try:
        nearby_stops = await bus_service.get_nearby_buses(lat, lon, radius_miles)
        return nearby_stops
    except Exception as e:
        logger.exception(f"Error getting nearby stops: {e}")
        raise HTTPException(status_code=500, detail=str(e))
