# backend/app/api/routes/transit.py

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas.transit import (
    RouteRequest,
    RouteResponse,
    TransitMode,
    StopDetail,
    RoutePreferences,
    TransitSegment,
    StopInfo,
    FromStop,
    NearbyBusResponse,
    BusInfo
)
from app.services.route_finder import (
    get_optimal_route,
    find_stops_in_radius,
    get_route_realtime_data
)
from app.db.database import get_db
from app.utils.json_cleaner import clean_api_response
from app.utils.xml_parser import xml_to_json
from app.services.scheduler_service import SchedulerService
import logging
from geopy.distance import geodesic
from datetime import datetime
import json

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/route", response_model=RouteResponse)
async def find_route(
    start_lat: float = Query(..., description="Starting point latitude"),
    start_lon: float = Query(..., description="Starting point longitude"),
    end_lat: float = Query(..., description="Ending point latitude"),
    end_lon: float = Query(..., description="Ending point longitude"),
    preferences: Optional[RoutePreferences] = None,
    db: Session = Depends(get_db)
):
    try:
        if not preferences:
            preferences = RoutePreferences()

        # Calculate route
        route = get_optimal_route(
            start_lat=start_lat,
            start_lon=start_lon,
            end_lat=end_lat,
            end_lon=end_lon,
            preferences=preferences,
            db=db
        )

        if not route:
            raise ValueError("No route found")

        # Clean the route data
        cleaned_route = clean_api_response(json.dumps(route))

        # Create RouteResponse model with cleaned data
        response = RouteResponse(
            total_time_minutes=cleaned_route.get("total_time_minutes", 0),
            total_cost_usd=cleaned_route.get("total_cost_usd", 0),
            total_distance_miles=cleaned_route.get("total_distance_miles", 0),
            segments=[
                TransitSegment(
                    mode=segment.get("mode", "walk"),
                    from_stop=FromStop(
                        name=segment["from_stop"]["name"],
                        lat=float(segment["from_stop"]["lat"]),
                        lon=float(segment["from_stop"]["lon"])
                    ) if segment.get("from_stop") else None,
                    to_stop=FromStop(
                        name=segment["to_stop"]["name"],
                        lat=float(segment["to_stop"]["lat"]),
                        lon=float(segment["to_stop"]["lon"])
                    ) if segment.get("to_stop") else None,
                    time_minutes=float(segment.get("time_minutes", 0)),
                    distance_miles=float(segment.get("distance_miles", 0)),
                    cost_usd=float(segment.get("cost_usd", 0)),
                    line_name=segment.get("line_name"),
                    direction=segment.get("direction"),
                    stops=[
                        StopInfo(
                            name=stop["name"],
                            lat=float(stop["lat"]),
                            lon=float(stop["lon"]),
                            arrival_time=stop.get("arrival_time"),
                            departure_time=stop.get("departure_time")
                        )
                        for stop in segment.get("stops", [])
                    ] if segment.get("stops") else []
                )
                for segment in cleaned_route.get("segments", [])
            ],
            delays=cleaned_route.get("delays"),
            accessibility=cleaned_route.get("accessibility"),
            weather_impact=cleaned_route.get("weather_impact")
        )

        return response

    except Exception as e:
        logger.error(f"Route calculation error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while calculating the route"
        )

@router.get("/stops/nearby", response_model=List[StopDetail])
async def find_nearby_stops(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius: float = Query(0.5, description="Search radius in miles"),
    transit_type: Optional[str] = Query(None, description="Filter by transit type (bus/bart)"),
    db: Session = Depends(get_db)
):
    """Find stops near a location"""
    try:
        stops = find_stops_in_radius(
            lat=lat,
            lon=lon,
            radius=radius,
            transit_type=transit_type,
            db=db
        )
        return stops
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/route/realtime")
async def get_realtime_updates(
    route_id: str = Query(..., description="Route ID to get updates for"),
    db: Session = Depends(get_db)
):
    """Get real-time updates for a route"""
    try:
        updates = get_route_realtime_data(route_id=route_id, db=db)
        
        # If updates are in XML format, convert to JSON
        if isinstance(updates, str) and updates.strip().startswith('<?xml'):
            updates = xml_to_json(updates)
            
        # Clean the JSON response
        cleaned_updates = clean_api_response(json.dumps(updates))
        
        return cleaned_updates
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/nearby-buses", response_model=List[NearbyBusResponse])
async def get_nearby_buses(
    lat: float = Query(..., description="User's latitude"),
    lon: float = Query(..., description="User's longitude"),
    radius: float = Query(0.5, description="Search radius in miles"),
    db: Session = Depends(get_db)
):
    """Get real-time bus information for stops near the user's location"""
    try:
        # ... existing validation code ...

        # Find nearby stops
        stops = find_stops_in_radius(
            lat=lat,
            lon=lon,
            radius=radius,
            transit_type="bus",
            db=db
        )

        if not stops:
            return []

        # Clean stops data
        cleaned_stops = [clean_api_response(json.dumps(stop)) for stop in stops]

        # Get real-time data for each stop
        responses = []
        for stop in cleaned_stops:
            # Convert dictionary to StopDetail if needed
            if isinstance(stop, dict):
                stop = StopDetail(**stop)

            # Calculate distance to stop
            distance = geodesic(
                (lat, lon),
                (float(stop.stop_lat), float(stop.stop_lon))
            ).meters

            # Get real-time data for this stop
            realtime_data = get_route_realtime_data(stop.stop_id, db)
            
            if not realtime_data:
                continue

            # If realtime data is XML, convert to JSON
            if isinstance(realtime_data, str) and realtime_data.strip().startswith('<?xml'):
                realtime_data = xml_to_json(realtime_data)

            # Clean realtime data
            cleaned_realtime = clean_api_response(json.dumps(realtime_data))

            # Process bus information
            buses = []
            for vehicle in cleaned_realtime.get("vehicles", []):
                bus_info = BusInfo(
                    line_name=vehicle.get("line_name", ""),
                    direction=vehicle.get("direction", ""),
                    next_arrival=vehicle.get("next_arrival"),
                    next_departure=vehicle.get("next_departure"),
                    destination=vehicle.get("destination", ""),
                    wheelchair_accessible=vehicle.get("wheelchair_accessible", True),
                    vehicle_location=vehicle.get("location"),
                    occupancy=vehicle.get("occupancy")
                )
                buses.append(bus_info)

            if buses:
                response = NearbyBusResponse(
                    stop_id=stop.stop_id,
                    stop_name=stop.stop_name,
                    stop_lat=float(stop.stop_lat),
                    stop_lon=float(stop.stop_lon),
                    distance_meters=round(distance, 2),
                    buses=buses,
                    last_updated=datetime.utcnow().isoformat()
                )
                responses.append(response)

        return responses

    except Exception as e:
        logger.error(f"Error in get_nearby_buses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/nearby-buses", response_model=List[NearbyBusResponse])
async def get_nearby_buses(
    lat: float = Query(..., description="User's latitude"),
    lon: float = Query(..., description="User's longitude"),
    radius: float = Query(0.5, description="Search radius in miles"),
    db: Session = Depends(get_db)
):
    """
    Get real-time bus information for stops near the user's location
    """
    try:
        # Validate coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            raise ValueError("Invalid coordinates")

        # Find nearby stops
        stops = find_stops_in_radius(
            lat=lat,
            lon=lon,
            radius=radius,
            transit_type="bus",  # Only get bus stops
            db=db
        )

        if not stops:
            return []

        # Get real-time data for each stop
        responses = []
        for stop in stops:
            # Convert dictionary to StopDetail if needed
            if isinstance(stop, dict):
                stop = StopDetail(**stop)

            # Calculate distance to stop
            distance = geodesic(
                (lat, lon),
                (stop.stop_lat, stop.stop_lon)
            ).meters

            # Get real-time data for this stop
            realtime_data = get_route_realtime_data(stop.stop_id, db)
            
            if not realtime_data:
                continue

            # Process bus information
            buses = []
            for vehicle in realtime_data.get("vehicles", []):
                bus_info = BusInfo(
                    line_name=vehicle.get("line_name", ""),
                    direction=vehicle.get("direction", ""),
                    next_arrival=vehicle.get("next_arrival"),
                    next_departure=vehicle.get("next_departure"),
                    destination=vehicle.get("destination", ""),
                    wheelchair_accessible=vehicle.get("wheelchair_accessible", True),
                    vehicle_location=vehicle.get("location"),
                    occupancy=vehicle.get("occupancy")
                )
                buses.append(bus_info)

            if buses:
                response = NearbyBusResponse(
                    stop_id=stop.stop_id,
                    stop_name=stop.stop_name,
                    stop_lat=stop.stop_lat,
                    stop_lon=stop.stop_lon,
                    distance_meters=round(distance, 2),
                    buses=buses,
                    last_updated=datetime.utcnow().isoformat()
                )
                responses.append(response)

        return responses

    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        raise HTTPException(
            status_code=422,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error getting nearby buses: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while fetching nearby bus information"
        )
        
scheduler_service = SchedulerService()

@router.get("/bus-schedule")
async def get_bus_schedule(
    destination: str = Query(..., description="Destination stop name or ID"),
    arrival_time: str = Query(..., description="Required arrival time in ISO format"),
    stop_id: Optional[str] = Query(None, description="Specific stop ID to check")
):
    """
    Get the best bus option for a given destination and arrival time.
    """
    try:
        # Validate arrival time format
        try:
            datetime.fromisoformat(arrival_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Invalid arrival time format. Use ISO format (e.g., 2024-03-20T10:00:00Z)"
            )

        # Get best bus option
        best_bus = await scheduler_service.get_best_bus_for_arrival(
            destination=destination,
            arrival_time=arrival_time,
            stop_id=stop_id
        )

        if not best_bus:
            return {
                "message": "No suitable bus found for the given criteria",
                "destination": destination,
                "arrival_time": arrival_time
            }

        return best_bus

    except Exception as e:
        logger.error(f"Error getting bus schedule: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while fetching bus schedule"
        )

@router.get("/stop-schedule")
async def get_stop_schedule(
    stop_id: str = Query(..., description="Stop ID to get schedule for"),
    line_id: Optional[str] = Query(None, description="Specific line ID to filter by")
):
    """
    Get the schedule for a specific stop.
    """
    try:
        schedule = await scheduler_service.get_schedule_for_stop(
            stop_id=stop_id,
            line_id=line_id
        )

        if not schedule:
            return {
                "message": "No schedule found for the given stop",
                "stop_id": stop_id
            }

        return schedule

    except Exception as e:
        logger.error(f"Error getting stop schedule: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while fetching stop schedule"
        )