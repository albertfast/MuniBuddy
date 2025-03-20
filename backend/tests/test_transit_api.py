# backend/tests/test_transit_api.py

import os
import sys

# Change working directory to backend folder
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add project root to Python path
sys.path.insert(0, os.getcwd())

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock
from app.main import app
from app.database import get_db
from app.schemas.transit import TransitMode
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base

class TestDatabase:
    def __init__(self):
        self.engine = create_engine('postgresql://myuser:mypassword@localhost:5432/munibuddy_test')
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.session = self.SessionLocal()

    def cleanup(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

client = TestClient(app)

# Test database setup
@pytest.fixture
def db():
    """Test database session"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Mock data
@pytest.fixture
def mock_stops():
    """Sample stop data for testing"""
    return [
        {
            'stop_id': '1234',
            'stop_name': 'Test Stop 1',
            'stop_lat': 37.7749,
            'stop_lon': -122.4194,
            'wheelchair_accessible': True,
            'covered_waiting_area': True
        },
        {
            'stop_id': 'BART_TEST',
            'stop_name': 'Test BART Station',
            'stop_lat': 37.7847,
            'stop_lon': -122.4079,
            'wheelchair_accessible': True,
            'covered_waiting_area': True
        }
    ]

@pytest.fixture
def mock_route():
    """Sample route data for testing"""
    def _mock_route(mode=TransitMode.fastest):
        return {
            'segments': [{
                'mode': mode.value,
                'from_stop': {
                    'name': 'Test Stop 1',
                    'lat': 37.7749,
                    'lon': -122.4194
                },
                'to_stop': {
                    'name': 'Test Stop 2',
                    'lat': 37.7847,
                    'lon': -122.4079
                },
                'stops': [{
                    'name': 'Test Stop 1',
                    'lat': 37.7749,
                    'lon': -122.4194,
                    'arrival_time': '2024-03-19T10:00:00',
                    'departure_time': '2024-03-19T10:05:00'
                }, {
                    'name': 'Test Stop 2',
                    'lat': 37.7847,
                    'lon': -122.4079,
                    'arrival_time': '2024-03-19T10:15:00',
                    'departure_time': '2024-03-19T10:20:00'
                }],
                'time_minutes': 15.0,
                'distance_miles': 1.2,
                'cost_usd': 2.50,
                'line_name': 'Test Line',
                'direction': 'Inbound'
            }],
            'total_cost_usd': 3.5,
            'total_distance_miles': 2.8,
            'total_time_minutes': 25.5,
            'delays': None,
            'accessibility': {
                'wheelchair_accessible': True,
                'has_stairs': False
            },
            'weather_impact': {
                'condition': 'clear',
                'impact_level': 'low'
            }
        }
    return _mock_route

class TestTransitAPI:
    def test_find_route_success(self, db, mock_route):
        """Test successful route finding"""
        with patch('app.api.routes.transit.get_optimal_route', return_value=mock_route(TransitMode.fastest)):
            response = client.get("/api/transit/route", params={
                "start_lat": 37.7749,
                "start_lon": -122.4194,
                "end_lat": 37.7847,
                "end_lon": -122.4079,
                "mode": "fastest",
                "wheelchair": False,
                "max_walking": 0.5
            })
            assert response.status_code == 200
            assert response.json() == mock_route(TransitMode.fastest)

    def test_find_route_invalid_coordinates(self, db):
        """Test route finding with invalid coordinates"""
        response = client.get("/api/transit/route", params={
            "start_lat": 200,  # Invalid latitude
            "start_lon": -122.4194,
            "end_lat": 37.7847,
            "end_lon": -122.4079
        })
        assert response.status_code == 422

    def test_find_nearby_stops_success(self, db, mock_stops):
        """Test successful nearby stops search"""
        with patch('app.api.routes.transit.find_stops_in_radius', return_value=mock_stops):
            response = client.get("/api/transit/stops/nearby", params={
                "lat": 37.7749,
                "lon": -122.4194,
                "radius": 0.5
            })
            assert response.status_code == 200
            assert response.json() == mock_stops

    def test_find_nearby_stops_filter_by_type(self, db, mock_stops):
        """Test nearby stops search with transit type filter"""
        with patch('app.api.routes.transit.find_stops_in_radius') as mock_find:
            mock_find.return_value = [mock_stops[1]]  # Only BART station
            response = client.get("/api/transit/stops/nearby", params={
                "lat": 37.7749,
                "lon": -122.4194,
                "radius": 0.5,
                "transit_type": "bart"
            })
            assert response.status_code == 200
            assert response.json() == [mock_stops[1]]

    def test_realtime_updates_success(self, db):
        """Test successful real-time updates retrieval"""
        mock_updates = {
            "route_id": "TEST_ROUTE",
            "vehicles": [
                {
                    "vehicle_id": "1234",
                    "lat": 37.7749,
                    "lon": -122.4194,
                    "heading": 90,
                    "speed": 25,
                    "delay": 120  # 2 minutes delay
                }
            ]
        }
        with patch('app.api.routes.transit.get_route_realtime_data', return_value=mock_updates):
            response = client.get("/api/transit/route/realtime", params={
                "route_id": "TEST_ROUTE"
            })
            assert response.status_code == 200
            assert response.json() == mock_updates

    def test_realtime_updates_invalid_route(self, db):
        """Test real-time updates with invalid route ID"""
        with patch('app.api.routes.transit.get_route_realtime_data', side_effect=Exception("Route not found")):
            response = client.get("/api/transit/route/realtime", params={
                "route_id": "INVALID_ROUTE"
            })
            assert response.status_code == 500

    @pytest.mark.parametrize("mode", [
        TransitMode.fastest,
        TransitMode.cheapest,
        TransitMode.bus,
        TransitMode.bart,
        TransitMode.combined
    ])
    def test_route_finding_different_modes(self, db, mock_route, mode):
        """Test route finding with different transit modes"""
        with patch('app.api.routes.transit.get_optimal_route', return_value=mock_route(mode)):
            response = client.get("/api/transit/route", params={
                "start_lat": 37.7749,
                "start_lon": -122.4194,
                "end_lat": 37.7847,
                "end_lon": -122.4079,
                "mode": mode.value
            })
            assert response.status_code == 200
            assert response.json() == mock_route(mode)

    def test_accessibility_requirements(self, db, mock_route):
        """Test route finding with accessibility requirements"""
        with patch('app.api.routes.transit.get_optimal_route', return_value=mock_route()):
            response = client.get("/api/transit/route", params={
                "start_lat": 37.7749,
                "start_lon": -122.4194,
                "end_lat": 37.7847,
                "end_lon": -122.4079,
                "wheelchair": True,
                "avoid_stairs": True
            })
            assert response.status_code == 200
            assert response.json() == mock_route()

    def test_get_nearby_buses_success(self, db, mock_stops):
        """Test successful nearby buses retrieval"""
        mock_realtime_data = {
            "vehicles": [
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
        }

        with patch('app.api.routes.transit.find_stops_in_radius', return_value=mock_stops), \
             patch('app.api.routes.transit.get_route_realtime_data', return_value=mock_realtime_data):
            
            response = client.get("/api/transit/nearby-buses", params={
                "lat": 37.7749,
                "lon": -122.4194,
                "radius": 0.5
            })
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) > 0
            assert "stop_id" in data[0]
            assert "stop_name" in data[0]
            assert "buses" in data[0]
            assert len(data[0]["buses"]) > 0
            assert data[0]["buses"][0]["line_name"] == "Test Line"

    def test_get_nearby_buses_invalid_coordinates(self, db):
        """Test nearby buses with invalid coordinates"""
        response = client.get("/api/transit/nearby-buses", params={
            "lat": 200,  # Invalid latitude
            "lon": -122.4194,
            "radius": 0.5
        })
        assert response.status_code == 422

def get_sample_route():
    """Sample route data for testing"""
    return {
        "route_id": "test_route",
        "status": "OK"
    }