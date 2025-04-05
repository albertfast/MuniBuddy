import pytest
from unittest.mock import patch, MagicMock, ANY
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.engine import Result, Row
import json
import os
from datetime import datetime

# Ensure the app directory is in the path for imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Create mock settings first
mock_settings = MagicMock()
mock_settings.DEFAULT_AGENCY = "SFMTA"
mock_settings.GTFS_PATHS = {"muni": "/fake/path/muni", "bart": "/fake/path/bart"}
mock_settings.API_KEY = "FAKE_API_KEY"
mock_settings.REDIS_HOST = "mock_redis"
mock_settings.REDIS_PORT = 6379
mock_settings.DATABASE_URL = "postgresql://user:pass@mock_db/testdb"

# Apply patches before importing the module
patches = [
    patch('app.config.settings', mock_settings),
    patch('app.route_finder.settings', mock_settings),
    
    # Create mock redis instance
    patch('redis.Redis', return_value=MagicMock()),
    patch('app.route_finder.Redis', return_value=MagicMock()),
    
    # Mock requests.get
    patch('requests.get', MagicMock()),
    patch('app.route_finder.requests.get', MagicMock()),
    
    # Mock SQLAlchemy
    patch('sqlalchemy.create_engine', return_value=MagicMock()),
    patch('app.route_finder.create_engine', return_value=MagicMock()),
    patch('sqlalchemy.orm.sessionmaker', return_value=MagicMock()),
    patch('app.route_finder.sessionmaker', return_value=MagicMock()),
    
    # Mock os.makedirs
    patch('os.makedirs'),
    patch('app.route_finder.os.makedirs')
]

# Start all patches
for p in patches:
    p.start()

# NOW import your actual route finder module
from app import route_finder

# Create test fixtures
@pytest.fixture
def mock_db_session():
    """Provides a mock SQLAlchemy session."""
    db = MagicMock(spec=Session)
    
    # Configure mock execute to return a mock Result
    mock_result = MagicMock(spec=Result)
    db.execute.return_value = mock_result
    
    # Configure fetchall to return empty by default
    mock_result.fetchall.return_value = []
    
    # Configure fetchone to return None by default
    mock_result.fetchone.return_value = None
    
    return db

@pytest.fixture
def reset_all_mocks():
    """Reset all mocks before each test."""
    route_finder.redis.reset_mock()
    route_finder.requests.get.reset_mock()
    
    # Default behavior: cache miss
    route_finder.redis.get.return_value = None
    
    # Default behavior: empty API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Siri": {"ServiceDelivery": {"VehicleMonitoringDelivery": [{"VehicleActivity": []}]}}
    }
    route_finder.requests.get.return_value = mock_response

# --- Test Functions ---

def test_find_nearest_stop_success(mock_db_session):
    """Test finding the nearest stop successfully."""
    # Setup mock response
    mock_row = MagicMock(spec=Row)
    mock_row._mapping = {
        "stop_id": "4212",
        "stop_name": "Powell St Station",
        "stop_lat": 37.7844,
        "stop_lon": -122.4078,
        "distance": 0.12
    }
    mock_db_session.execute.return_value.fetchone.return_value = mock_row
    
    # Call function
    result = route_finder.find_nearest_stop(37.78, -122.41, mock_db_session)
    
    # Verify results
    assert result is not None
    assert result["stop_id"] == "4212"
    assert result["stop_name"] == "Powell St Station"
    assert result["distance"] == 0.12
    mock_db_session.execute.assert_called_once()

def test_find_nearest_stop_no_result(mock_db_session):
    """Test when no stops are found nearby."""
    # Setup mock to return None
    mock_db_session.execute.return_value.fetchone.return_value = None
    
    # Call function
    result = route_finder.find_nearest_stop(37.78, -122.41, mock_db_session)
    
    # Verify results
    assert result is None
    mock_db_session.execute.assert_called_once()

def test_find_nearest_stop_error(mock_db_session):
    """Test handling database errors."""
    # Setup mock to raise exception
    mock_db_session.execute.side_effect = Exception("Database error")
    
    # Call function and check for exception
    with pytest.raises(Exception, match="Database error"):
        route_finder.find_nearest_stop(37.78, -122.41, mock_db_session)

def test_get_live_bus_positions_success():
    """Test parsing live bus data from API."""
    # Setup mock response with sample data
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Siri": {
            "ServiceDelivery": {
                "VehicleMonitoringDelivery": [{
                    "VehicleActivity": [
                        {
                            "MonitoredVehicleJourney": {
                                "LineRef": "38",
                                "VehicleLocation": {"Latitude": 37.78, "Longitude": -122.41}
                            }
                        },
                        {
                            "MonitoredVehicleJourney": {
                                "LineRef": "N",
                                "VehicleLocation": {"Latitude": 37.77, "Longitude": -122.40}
                            }
                        }
                    ]
                }]
            }
        }
    }
    route_finder.requests.get.return_value = mock_response
    
    # Call function
    result = route_finder.get_live_bus_positions()
    
    # Verify results
    assert len(result) == 2
    assert result[0]["MonitoredVehicleJourney"]["LineRef"] == "38"
    assert result[1]["MonitoredVehicleJourney"]["LineRef"] == "N"
    route_finder.requests.get.assert_called_once()

def test_get_live_bus_positions_api_error():
    """Test handling API errors."""
    # Setup mock to simulate HTTP error
    mock_response = MagicMock()
    mock_response.status_code = 500
    route_finder.requests.get.return_value = mock_response
    
    # Call function
    result = route_finder.get_live_bus_positions()
    
    # Verify results - should be empty list on error
    assert result == []
    route_finder.requests.get.assert_called_once()

def test_get_live_bus_positions_json_error():
    """Test handling malformed JSON responses."""
    # Setup mock to return invalid JSON
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
    route_finder.requests.get.return_value = mock_response
    
    # Call function
    result = route_finder.get_live_bus_positions()
    
    # Verify results - should be empty list on JSON error
    assert result == []
    route_finder.requests.get.assert_called_once()

def test_build_transit_graph(mock_db_session):
    """Test building the transit graph."""
    # Setup mock responses for stops and connections
    stops_data = [
        {"stop_id": "A", "stop_lat": 37.78, "stop_lon": -122.41},
        {"stop_id": "B", "stop_lat": 37.77, "stop_lon": -122.40},
        {"stop_id": "C", "stop_lat": 37.79, "stop_lon": -122.42}
    ]
    
    connections_data = [
        {"from_stop": "A", "to_stop": "B", "route_id": "38"},
        {"from_stop": "B", "to_stop": "C", "route_id": "N"}
    ]
    
    # Configure mock to return these results
    def mock_execute_side_effect(query, *args, **kwargs):
        query_str = str(query)
        mock_result = MagicMock(spec=Result)
        if "SELECT DISTINCT stop_id" in query_str:
            mock_result.fetchall.return_value = [
                {"stop_id": s["stop_id"], "stop_lat": s["stop_lat"], "stop_lon": s["stop_lon"]} 
                for s in stops_data
            ]
        elif "SELECT DISTINCT s1.stop_id" in query_str:
            mock_result.fetchall.return_value = [
                {"from_stop": c["from_stop"], "to_stop": c["to_stop"], "route_id": c["route_id"]}
                for c in connections_data
            ]
        return mock_result
        
    mock_db_session.execute.side_effect = mock_execute_side_effect
    
    # Call function
    graph = route_finder.build_transit_graph(mock_db_session)
    
    # Verify graph has expected nodes and edges
    assert len(graph.nodes) == 3  # A, B, C
    assert len(graph.edges) == 2  # A->B, B->C
    assert graph.has_edge("A", "B")
    assert graph.has_edge("B", "C")
    assert graph["A"]["B"]["route_id"] == "38"
    assert graph["B"]["C"]["route_id"] == "N"

def test_find_optimized_route_cache_hit(mock_db_session):
    """Test returning a cached route."""
    # Setup cache hit
    cached_route = {"route": ["A", "B", "C"], "details": "Optimal route"}
    route_finder.redis.get.return_value = json.dumps(cached_route)
    
    # Call function
    result = route_finder.find_optimized_route(37.78, -122.41, 37.79, -122.42, mock_db_session)
    
    # Verify results
    assert result == cached_route
    route_finder.redis.get.assert_called_once()
    # Ensure DB wasn't queried
    mock_db_session.execute.assert_not_called()

def test_find_optimized_route_no_start_stop(mock_db_session):
    """Test when no start stop is found."""
    # Setup - find_nearest_stop will return None for start
    with patch('app.route_finder.find_nearest_stop', side_effect=[None, {"stop_id": "END"}]):
        # Call function and check for exception
        with pytest.raises(HTTPException) as excinfo:
            route_finder.find_optimized_route(37.78, -122.41, 37.79, -122.42, mock_db_session)
        
        # Verify correct error
        assert excinfo.value.status_code == 404
        assert "No nearby stops found for starting point" in excinfo.value.detail

def test_find_optimized_route_no_end_stop(mock_db_session):
    """Test when no end stop is found."""
    # Setup - find_nearest_stop will return start but no end
    with patch('app.route_finder.find_nearest_stop', side_effect=[{"stop_id": "START"}, None]):
        # Call function and check for exception
        with pytest.raises(HTTPException) as excinfo:
            route_finder.find_optimized_route(37.78, -122.41, 37.79, -122.42, mock_db_session)
        
        # Verify correct error
        assert excinfo.value.status_code == 404
        assert "No nearby stops found for destination" in excinfo.value.detail

def test_find_optimized_route_no_route_found(mock_db_session):
    """Test when no route can be found between stops."""
    # Setup mocks
    start_stop = {"stop_id": "START", "stop_name": "Start Stop", "lat": 37.78, "lon": -122.41}
    end_stop = {"stop_id": "END", "stop_name": "End Stop", "lat": 37.79, "lon": -122.42}
    
    with patch('app.route_finder.find_nearest_stop', side_effect=[start_stop, end_stop]):
        with patch('app.route_finder.get_live_bus_positions', return_value=[]):
            with patch('app.route_finder.a_star_search', return_value=None):
                # Call function and check for exception
                with pytest.raises(HTTPException) as excinfo:
                    route_finder.find_optimized_route(37.78, -122.41, 37.79, -122.42, mock_db_session)
                
                # Verify correct error
                assert excinfo.value.status_code == 404
                assert "No optimal route found" in excinfo.value.detail

def test_find_optimized_route_success(mock_db_session):
    """Test successful route finding."""
    # Setup mocks
    start_stop = {"stop_id": "START", "stop_name": "Start Stop", "lat": 37.78, "lon": -122.41}
    end_stop = {"stop_id": "END", "stop_name": "End Stop", "lat": 37.79, "lon": -122.42}
    live_buses = [{"MonitoredVehicleJourney": {"LineRef": "38"}}]
    optimal_route = {
        "path": ["START", "MID", "END"], 
        "transfers": 1,
        "total_time": 15,
        "instructions": ["Take 38 from Start Stop", "Transfer to N at Mid Stop"]
    }
    
    with patch('app.route_finder.find_nearest_stop', side_effect=[start_stop, end_stop]):
        with patch('app.route_finder.get_live_bus_positions', return_value=live_buses):
            with patch('app.route_finder.a_star_search', return_value=optimal_route):
                # Call function
                result = route_finder.find_optimized_route(37.78, -122.41, 37.79, -122.42, mock_db_session)
                
                # Verify results
                assert result == optimal_route
                # Verify caching
                route_finder.redis.setex.assert_called_once_with(
                    "route:37.78,-122.41-37.79,-122.42",
                    ANY,  # Cache TTL
                    json.dumps(optimal_route)
                )

def test_a_star_search_no_path(mock_db_session):
    """Test A* search when no path exists."""
    # Setup graph with disconnected nodes
    graph = MagicMock()
    graph.nodes = {"START": {}, "END": {}}
    graph.has_edge.return_value = False
    
    with patch('app.route_finder.build_transit_graph', return_value=graph):
        # Call function
        result = route_finder.a_star_search(
            {"stop_id": "START", "lat": 37.78, "lon": -122.41},
            {"stop_id": "END", "lat": 37.79, "lon": -122.42},
            [],
            mock_db_session
        )
        
        # Verify no path found
        assert result is None

def test_calculate_distance():
    """Test the distance calculation function."""
    # Test points with known distance
    # San Francisco to Oakland ~12km
    distance = route_finder.calculate_distance(
        37.7749, -122.4194,  # SF
        37.8044, -122.2711   # Oakland
    )
    
    # Assert distance is approximately correct (within 0.5 km)
    assert 11.5 < distance < 12.5

def test_calculate_angle():
    """Test the angle calculation function."""
    # Test with known angles
    # East: 0 degrees
    east_angle = route_finder.calculate_angle(0, 0, 0, 1)
    assert -10 < east_angle < 10
    
    # North: 90 degrees
    north_angle = route_finder.calculate_angle(0, 0, 1, 0)
    assert 80 < north_angle < 100
    
    # West: 180 degrees
    west_angle = route_finder.calculate_angle(0, 0, 0, -1)
    assert 170 < west_angle < 190 or -190 < west_angle < -170
    
    # South: 270 degrees
    south_angle = route_finder.calculate_angle(0, 0, -1, 0)
    assert 260 < south_angle < 280 or -100 < south_angle < -80

# Clean up patches at the end
def teardown_module(module):
    for p in patches:
        p.stop()