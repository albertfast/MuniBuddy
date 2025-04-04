import pytest
from unittest.mock import patch, MagicMock, ANY
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.engine import Result
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

# Mock dataframes
mock_routes_df = MagicMock()
mock_trips_df = MagicMock()
mock_stops_df = MagicMock()
mock_stop_times_df = MagicMock()
mock_calendar_df = MagicMock()
mock_settings.get_gtfs_data.return_value = (
    mock_routes_df, mock_trips_df, mock_stops_df, mock_stop_times_df, mock_calendar_df
)

# Apply patches before importing the module
patches = [
    # Update this path to match your actual module path
    patch('backend.route_finder2.settings', mock_settings),
    
    # Create mock redis instance
    patch('backend.route_finder2.Redis', return_value=MagicMock()),
    
    # Mock requests.get
    patch('backend.route_finder2.requests.get', MagicMock()),
    
    # Mock SQLAlchemy
    patch('backend.route_finder2.create_engine', return_value=MagicMock()),
    patch('backend.route_finder2.sessionmaker', return_value=MagicMock()),
    
    # Mock os.makedirs
    patch('backend.route_finder2.os.makedirs')
]

# Start all patches
for p in patches:
    p.start()

# NOW import your actual route finder module (adjust path as needed)
from backend import route_finder2 as route_finder

# Stop patches if needed
# for p in patches:
#     p.stop()

# Create test fixtures
@pytest.fixture
def mock_db_session():
    """Provides a mock SQLAlchemy session."""
    db = MagicMock(spec=Session)
    # Configure mock execute results as needed by tests
    db.execute.return_value = MagicMock(spec=Result)
    return db

@pytest.fixture(autouse=True) # Ensure Redis mock is reset for each test
def reset_redis_mock():
    """Resets the Redis mock calls before each test."""
    route_finder.redis.reset_mock()
    # Default behavior: cache miss
    route_finder.redis.get.return_value = None

@pytest.fixture(autouse=True) # Ensure requests mock is reset for each test
def reset_requests_mock():
    """Resets the requests mock calls before each test."""
    route_finder.requests.get.reset_mock()
    # Default behavior: success, empty vehicles
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text.encode.return_value.decode.return_value = json.dumps({
        "Siri": {"ServiceDelivery": {"VehicleMonitoringDelivery": [{"VehicleActivity": []}]}}
    })
    route_finder.requests.get.return_value = mock_response


# --- Test Functions ---

def test_find_optimized_route_cache_hit(mock_db_session):
    """Test returning a cached route."""
    cached_data = {"route": ["stopA", "stopB"], "details": "Cached Route"}
    
    # Update to use the mock_redis_instance from the actual module
    route_finder.redis.get.return_value = json.dumps(cached_data)

    # Use the imported router functions directly
    result = route_finder.find_optimized_route(
        start_lat=37.1, start_lon=-122.1, end_lat=37.2, end_lon=-122.2, db=mock_db_session
    )

    assert result == cached_data
    route_finder.redis.get.assert_called_once_with("route:37.1,-122.1-37.2,-122.2")
    # Ensure DB or API calls were NOT made
    mock_db_session.execute.assert_not_called()

# Parameterize test cases for nearest stop finding
@pytest.mark.parametrize("db_return, expected_output, expect_exception", [
    # Case 1: Stop found
    ([( "123", "Stop Name", 37.123, -122.123, 0.1)], # Simulate fetchone returning a tuple/row
     {"stop_id": "123", "stop_name": "Stop Name", "lat": 37.123, "lon": -122.123, "distance": 0.1},
     False),
    # Case 2: No stop found
    ([], None, False),
    # Case 3: DB Error during query
    (None, None, True),
])
def test_find_nearest_stop(mock_db_session, db_return, expected_output, expect_exception):
    """Test finding the nearest stop."""
    if expect_exception:
        mock_db_session.execute.side_effect = Exception("DB Error")
        with pytest.raises(Exception, match="DB Error"):
            route_finder.find_nearest_stop(37.1, -122.1, mock_db_session)
    elif not db_return: # No stop found case
        mock_result = MagicMock(spec=Result)
        mock_result.fetchone.return_value = None # Simulate fetchone() returning None
        mock_db_session.execute.return_value = mock_result
        result = route_finder.find_nearest_stop(37.1, -122.1, mock_db_session)
        assert result is None
    else: # Stop found case
        mock_result = MagicMock(spec=Result)
        mock_result.fetchone.return_value = db_return[0] # Simulate fetchone() returning the row
        mock_db_session.execute.return_value = mock_result
        result = route_finder.find_nearest_stop(37.1, -122.1, mock_db_session)
        assert result == expected_output

    # Verify the query structure if needed (can be complex with text())
    mock_db_session.execute.assert_called_once()
    # print(mock_db_session.execute.call_args) # Debug call arguments if needed


@patch('backend.route_finder2.find_nearest_stop')
@patch('backend.route_finder2.get_live_bus_positions')
@patch('backend.route_finder2.a_star_search')
def test_find_optimized_route_no_stops_found(mock_a_star, mock_get_live, mock_find_nearest, mock_db_session):
    """Test HTTP Exception when no nearby stops are found."""
    mock_find_nearest.return_value = None # Simulate find_nearest_stop returning None

    with pytest.raises(HTTPException) as exc_info:
        route_finder.find_optimized_route(37.1, -122.1, 37.2, -122.2, mock_db_session)

    assert exc_info.value.status_code == 404
    assert "No nearby stops found" in exc_info.value.detail
    mock_find_nearest.assert_called() # Ensure it was called at least once
    mock_get_live.assert_not_called() # Should not proceed if stops aren't found
    mock_a_star.assert_not_called()

@patch('backend.route_finder2.find_nearest_stop')
@patch('backend.route_finder2.get_live_bus_positions')
@patch('backend.route_finder2.a_star_search')
def test_find_optimized_route_no_live_data(mock_a_star, mock_get_live, mock_find_nearest, mock_db_session):
    """Test HTTP Exception when live bus data is unavailable."""
    # Simulate stops being found
    mock_find_nearest.side_effect = [
        {"stop_id": "start", "lat": 37.1, "lon": -122.1},
        {"stop_id": "end", "lat": 37.2, "lon": -122.2}
    ]
    mock_get_live.return_value = [] # Simulate get_live_bus_positions returning empty list

    with pytest.raises(HTTPException) as exc_info:
        route_finder.find_optimized_route(37.1, -122.1, 37.2, -122.2, mock_db_session)

    assert exc_info.value.status_code == 500
    assert "Live data unavailable" in exc_info.value.detail
    mock_find_nearest.assert_called()
    mock_get_live.assert_called_once()
    mock_a_star.assert_not_called()

@patch('backend.route_finder2.find_nearest_stop')
@patch('backend.route_finder2.get_live_bus_positions')
@patch('backend.route_finder2.a_star_search')
def test_find_optimized_route_no_route_found(mock_a_star, mock_get_live, mock_find_nearest, mock_db_session):
    """Test HTTP Exception when A* search finds no route."""
    start_stop_mock = {"stop_id": "start", "lat": 37.1, "lon": -122.1}
    end_stop_mock = {"stop_id": "end", "lat": 37.2, "lon": -122.2}
    live_buses_mock = [{"vehicle": "data"}]

    mock_find_nearest.side_effect = [start_stop_mock, end_stop_mock]
    mock_get_live.return_value = live_buses_mock
    mock_a_star.return_value = None # Simulate A* returning None

    with pytest.raises(HTTPException) as exc_info:
        route_finder.find_optimized_route(37.1, -122.1, 37.2, -122.2, mock_db_session)

    assert exc_info.value.status_code == 404
    assert "No optimal route found" in exc_info.value.detail
    mock_find_nearest.assert_called()
    mock_get_live.assert_called_once()
    mock_a_star.assert_called_once_with(start_stop_mock, end_stop_mock, live_buses_mock, mock_db_session)

@patch('backend.route_finder2.find_nearest_stop')
@patch('backend.route_finder2.get_live_bus_positions')
@patch('backend.route_finder2.a_star_search')
def test_find_optimized_route_success_cache_miss(mock_a_star, mock_get_live, mock_find_nearest, mock_db_session):
    """Test successful route finding and caching."""
    start_stop_mock = {"stop_id": "start", "lat": 37.1, "lon": -122.1}
    end_stop_mock = {"stop_id": "end", "lat": 37.2, "lon": -122.2}
    live_buses_mock = [{"vehicle": "data"}]
    found_route = ["start", "mid", "end"]

    mock_find_nearest.side_effect = [start_stop_mock, end_stop_mock]
    mock_get_live.return_value = live_buses_mock
    mock_a_star.return_value = found_route

    # Ensure cache miss
    route_finder.redis.get.return_value = None

    result = route_finder.find_optimized_route(37.1, -122.1, 37.2, -122.2, mock_db_session)

    assert result == found_route
    route_finder.redis.get.assert_called_once_with("route:37.1,-122.1-37.2,-122.2")
    mock_find_nearest.assert_called()
    mock_get_live.assert_called_once()
    mock_a_star.assert_called_once_with(start_stop_mock, end_stop_mock, live_buses_mock, mock_db_session)
    # Verify caching
    route_finder.redis.setex.assert_called_once_with(
        "route:37.1,-122.1-37.2,-122.2",
        300, # Cache timeout
        json.dumps(found_route)
    )

def test_get_live_bus_positions_success():
    """Test successful parsing of live bus positions."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Sample data structure based on the code's expectation
    sample_api_data = {
        "Siri": {
            "ServiceDelivery": {
                "VehicleMonitoringDelivery": [{
                    "VehicleActivity": [
                        {"vehicle": "1"}, {"vehicle": "2"}
                    ]
                }]
            }
        }
    }
    mock_response.text.encode.return_value.decode.return_value = json.dumps(sample_api_data)
    route_finder.requests.get.return_value = mock_response # Configure mock for this test

    result = route_finder.get_live_bus_positions()

    assert result == [{"vehicle": "1"}, {"vehicle": "2"}]
    route_finder.requests.get.assert_called_once_with(f"http://api.511.org/transit/VehicleMonitoring?api_key=FAKE_API_KEY&agency=SF")

def test_get_live_bus_positions_api_error():
    """Test handling of 511 API error."""
    mock_response = MagicMock()
    mock_response.status_code = 503 # Simulate API error
    route_finder.requests.get.return_value = mock_response # Configure mock for this test

    result = route_finder.get_live_bus_positions()

    assert result == [] # Expect empty list on error
    route_finder.requests.get.assert_called_once()

def test_get_live_bus_positions_json_error():
    """Test handling of invalid JSON from 511 API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text.encode.return_value.decode.return_value = "This is not JSON" # Invalid JSON
    route_finder.requests.get.return_value = mock_response # Configure mock for this test

    result = route_finder.get_live_bus_positions()

    assert result == [] # Expect empty list on JSON error
    route_finder.requests.get.assert_called_once()


# --- Placeholder Tests for Functions Not Directly Tested Above ---
# These would require more complex mocking of DB interactions and potentially
# the A* logic itself or its helper functions.

@pytest.mark.skip(reason="Requires complex DB mocking for graph/route logic")
def test_a_star_search_placeholder(mock_db_session):
     # Mock DB calls made by a_star_search and its helpers
     # Call route_finder.a_star_search(...)
     # Assert expected path or None
     pass

@pytest.mark.skip(reason="Requires complex DB mocking for graph build")
def test_build_transit_graph_placeholder(mock_db_session):
     # Mock DB calls returning stops and edges
     # Call route_finder.build_transit_graph()
     # Assert graph properties (nodes, edges) using route_finder.G
     pass

@pytest.mark.skip(reason="Requires complex DB mocking")
def test_get_routes_for_stop_placeholder(mock_db_session):
    # Mock db.execute for the specific queries in get_routes_for_stop
    # Call route_finder.get_routes_for_stop(...)
    # Assert the expected list of route dicts
    pass

@pytest.mark.skip(reason="Requires complex DB mocking")
def test_get_stops_for_route_placeholder(mock_db_session):
    # Mock db.execute for the specific queries in get_stops_for_route
    # Call route_finder.get_stops_for_route(...)
    # Assert the expected list of stop IDs forming the path
    pass

# Note: Testing functions like calculate_distance, calculate_angle, etc.,
# which are pure calculations, is straightforward and doesn't require mocking.
# You can add simple tests for them if desired.
def test_calculate_distance_pure():
    # Simple test without fixtures
    dist = route_finder.calculate_distance(0, 0, 0, 1) # Approx 1 degree lon at equator
    assert dist > 110 and dist < 112 # Roughly 111 km