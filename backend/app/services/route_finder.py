from typing import Tuple, List, Dict, Optional
from sqlalchemy.orm import Session
import logging
from app.schemas.transit import (
    RouteResponse,
    RoutePreferences,
    TransitSegment,
    StopDetail
)
from app.models import Base
from geopy.distance import geodesic
from datetime import datetime

logger = logging.getLogger(__name__)

def get_optimal_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    preferences: RoutePreferences,
    db: Session
) -> Dict:
    """
    Find the optimal route between two points based on user preferences
    """
    logger.info(f"Searching for route: ({start_lat}, {start_lon}) -> ({end_lat}, {end_lon})")
    try:
        # Find nearest stops
        start_stops = find_stops_in_radius(start_lat, start_lon, preferences.max_walking_distance, None, db)
        end_stops = find_stops_in_radius(end_lat, end_lon, preferences.max_walking_distance, None, db)

        if not start_stops or not end_stops:
            raise Exception("No stops found near start or end points")

        # Calculate routes based on mode
        routes = []
        mode_str = preferences.mode.value if hasattr(preferences.mode, 'value') else str(preferences.mode)
        
        if mode_str in ["fastest", "bus", "combined"]:
            bus_route = calculate_bus_route(start_stops[0], end_stops[0], preferences, db)
            if bus_route:
                routes.append(bus_route)

        if mode_str in ["fastest", "bart", "combined"]:
            bart_route = calculate_bart_route(start_stops[0], end_stops[0], preferences, db)
            if bart_route:
                routes.append(bart_route)

        if not routes:
            raise Exception("No suitable routes found")

        # Select best route
        best_route = select_best_route(routes, preferences)
        
        # Get real-time delays
        delays = get_route_realtime_data(best_route["route_id"], db) if "route_id" in best_route else None
        if delays:
            best_route["delays"] = delays

        # Add accessibility information
        if "segments" in best_route:
            accessibility_info = get_accessibility_info(best_route["segments"], db)
            if accessibility_info:
                best_route["accessibility"] = accessibility_info

        # Add weather impact
        weather_impact = get_weather_impact(best_route["segments"]) if "segments" in best_route else None
        if weather_impact:
            best_route["weather_impact"] = weather_impact

        return best_route

    except Exception as e:
        logger.error(f"Error finding route: {str(e)}")
        raise

def find_stops_in_radius(
    lat: float,
    lon: float,
    radius: float,
    transit_type: Optional[str],
    db: Session
) -> List[StopDetail]:
    """
    Find stops within a specified radius
    """
    try:
        # Mock data for testing
        # In production, this would query the database
        mock_stops = [
            StopDetail(
                stop_id="1234",
                stop_name="Test Stop 1",
                stop_lat=37.7749,
                stop_lon=-122.4194,
                wheelchair_accessible=True,
                covered_waiting_area=True
            ),
            StopDetail(
                stop_id="5678",
                stop_name="Test Stop 2",
                stop_lat=37.7847,
                stop_lon=-122.4079,
                wheelchair_accessible=True,
                covered_waiting_area=False
            )
        ]

        # Filter by transit type if specified
        if transit_type:
            if transit_type.lower() == "bart":
                return [stop for stop in mock_stops if "BART" in stop.stop_id]
            elif transit_type.lower() == "bus":
                return [stop for stop in mock_stops if "BART" not in stop.stop_id]

        return mock_stops

    except Exception as e:
        logger.error(f"Error finding stops in radius: {str(e)}")
        return []

def get_route_realtime_data(route_id: str, db: Session) -> Dict:
    """
    Get real-time data for a specific route from SFMTA API
    """
    try:
        # Mock data for testing
        # In production, this would fetch from SFMTA API
        mock_vehicles = [
            {
                "line_name": "Test Line",
                "direction": "Inbound",
                "next_arrival": "2024-03-19T10:00:00",
                "next_departure": "2024-03-19T10:05:00",
                "destination": "Test Destination",
                "wheelchair_accessible": True,
                "location": {"lat": 37.7749, "lon": -122.4194},
                "occupancy": "seatsAvailable"
            }
        ]

        return {
            "route_id": route_id,
            "vehicles": mock_vehicles,
            "last_updated": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching real-time data: {str(e)}")
        return {
            "route_id": route_id,
            "vehicles": [],
            "last_updated": datetime.utcnow().isoformat()
        }

def calculate_bus_route(start_stops, end_stops, preferences, db) -> Dict:
    """
    Helper function to calculate bus route
    """
    # TODO: Implement bus route calculation
    return {}

def calculate_bart_route(start_stops, end_stops, preferences, db) -> Dict:
    """
    Helper function to calculate BART route
    """
    # TODO: Implement BART route calculation
    return {}

def select_best_route(routes: List[Dict], preferences: RoutePreferences) -> Dict:
    """
    Helper function to select the best route from given options
    """
    if not routes:
        return None
    
    mode_str = preferences.mode.value if hasattr(preferences.mode, 'value') else str(preferences.mode)
    
    # Select route based on preferred mode
    if mode_str == "fastest":
        return min(routes, key=lambda r: r.get("total_time_minutes", float("inf")))
    elif mode_str == "cheapest":
        return min(routes, key=lambda r: r.get("total_cost_usd", float("inf")))
    else:
        # Select best route based on route score
        return max(routes, key=lambda r: calculate_route_score(r, preferences))

def calculate_route_score(route: Dict, preferences: RoutePreferences) -> float:
    """
    Helper function to calculate score for a route
    """
    score = 0.0
    
    # Basic metrics
    time_score = 100 - min(route.get("total_time_minutes", 0), 100)
    cost_score = 100 - min(route.get("total_cost_usd", 0) * 10, 100)
    
    # Accessibility score
    accessibility_score = 100 if route.get("accessibility", {}).get("wheelchair_accessible") else 0
    if preferences.avoid_stairs and route.get("accessibility", {}).get("has_stairs"):
        accessibility_score = 0
    
    # Weather impact
    weather_score = 100 - min(route.get("weather_impact", {}).get("impact_percentage", 0), 100)
    
    # Weighted sum
    weights = {
        "time": 0.4,
        "cost": 0.3,
        "accessibility": 0.2,
        "weather": 0.1
    }
    
    score = (
        time_score * weights["time"] +
        cost_score * weights["cost"] +
        accessibility_score * weights["accessibility"] +
        weather_score * weights["weather"]
    )
    
    return score

def get_accessibility_info(segments: List[TransitSegment], db: Session) -> Dict:
    """
    Helper function to get accessibility information for route segments
    """
    return {
        "wheelchair_accessible": True,
        "has_stairs": False,
        "has_elevators": True
    }

def get_weather_impact(segments: List[TransitSegment]) -> Dict:
    """
    Helper function to get weather impact for route segments
    """
    return {
        "impact_percentage": 0,
        "conditions": "clear",
        "alerts": []
    } 