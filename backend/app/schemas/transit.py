from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class TransitMode(str, Enum):
    fastest = "fastest"
    cheapest = "cheapest"
    bus = "bus"
    bart = "bart"
    combined = "combined"

class StopDetail(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    wheelchair_accessible: bool = True
    covered_waiting_area: bool = False

class FromStop(BaseModel):
    name: str
    lat: float
    lon: float

class StopInfo(BaseModel):
    name: str
    lat: float
    lon: float
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None

class TransitSegment(BaseModel):
    mode: str
    from_stop: Optional[FromStop] = None
    to_stop: Optional[FromStop] = None
    time_minutes: float
    distance_miles: float
    cost_usd: Optional[float] = None
    line_name: Optional[str] = None
    direction: Optional[str] = None
    stops: List[StopInfo] = []

class RoutePreferences(BaseModel):
    mode: TransitMode = TransitMode.fastest
    wheelchair_access: bool = False
    max_walking_distance: float = 0.5
    avoid_stairs: bool = False
    prefer_covered_waiting: bool = False

class RouteRequest(BaseModel):
    start_lat: float = Field(..., description="Starting point latitude")
    start_lon: float = Field(..., description="Starting point longitude")
    end_lat: float = Field(..., description="Destination point latitude")
    end_lon: float = Field(..., description="Destination point longitude")
    preferences: RoutePreferences = Field(default_factory=RoutePreferences)

class RouteResponse(BaseModel):
    total_time_minutes: float
    total_cost_usd: float
    total_distance_miles: float
    segments: List[TransitSegment]
    delays: Optional[Dict] = None
    accessibility: Optional[Dict] = None
    weather_impact: Optional[Dict] = None

class BusInfo(BaseModel):
    line_name: str
    direction: str
    next_arrival: Optional[str] = None
    next_departure: Optional[str] = None
    destination: str
    wheelchair_accessible: bool = True
    vehicle_location: Optional[Dict[str, float]] = None
    occupancy: Optional[str] = None

class NearbyBusResponse(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    distance_meters: float
    buses: List[BusInfo]
    last_updated: str 