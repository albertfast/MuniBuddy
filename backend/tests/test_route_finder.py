import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import json
from app.main import app

api_base_url = 'https://munibuddy.live/api'


# Use TestClient to simulate API requests
client = TestClient(app)

# Sample route cache key
cache_key = "route:37.7749,-122.4194-37.7849,-122.4074"
mock_route = ["stop_123", "stop_456", "stop_789"]

# Patch Redis and external dependencies
@pytest.fixture(autouse=True)
def patch_dependencies():
    with patch("app.route_finder.redis") as mock_redis, \
         patch("app.route_finder.get_live_bus_positions") as mock_live, \
         patch("app.route_finder.find_nearest_stop") as mock_nearest, \
         patch("app.route_finder.a_star_search") as mock_astar:

        # Mock Redis behavior
        mock_redis.get.return_value = None
        mock_redis.setex = MagicMock()

        # Mock nearest stop for start and end
        mock_nearest.side_effect = [
            {"stop_id": "start_001", "lat": 37.7749, "lon": -122.4194},
            {"stop_id": "end_001", "lat": 37.7849, "lon": -122.4074}
        ]

        # Mock live buses
        mock_live.return_value = [{"vehicle_id": "bus_01"}]

        # Mock A* route
        mock_astar.return_value = ["stop_123", "stop_456", "stop_789"]

        yield


def test_valid_route():
    response = client.get("/optimized-route", params={
        "start_lat": 37.7749,
        "start_lon": -122.4194,
        "end_lat": 37.7849,
        "end_lon": -122.4074
    })
    assert response.status_code == 200
    assert response.json() == mock_route
    print(f"\033[92m✓ Found optimized route with {len(mock_route)} stops\033[0m")


def test_missing_nearby_stop(patch_dependencies):
    with patch("app.api.routes.route_finder.find_nearest_stop") as mock_nearest:
        mock_nearest.side_effect = [None, None]
        response = client.get("/optimized-route", params={
            "start_lat": 0.0,
            "start_lon": 0.0,
            "end_lat": 0.0,
            "end_lon": 0.0
        })
        assert response.status_code == 404
        print(f"\033[93m⚠️ No nearby start or end stop found\033[0m")


def test_live_data_failure():
    with patch("app.api.routes.route_finder.get_live_bus_positions", return_value=None):
        response = client.get("/optimized-route", params={
            "start_lat": 37.7749,
            "start_lon": -122.4194,
            "end_lat": 37.7849,
            "end_lon": -122.4074
        })
        assert response.status_code == 500
        print(f"\033[91m✗ Live bus data unavailable — gracefully handled\033[0m")


def test_route_caching():
    with patch("app.api.routes.route_finder.redis.get", return_value=json.dumps(mock_route)):
        response = client.get("/optimized-route", params={
            "start_lat": 37.7749,
            "start_lon": -122.4194,
            "end_lat": 37.7849,
            "end_lon": -122.4074
        })
        assert response.status_code == 200
        assert response.json() == mock_route
        print(f"\033[94mℹ️ Served route from Redis cache successfully\033[0m")


def test_no_optimal_route():
    with patch("app.api.routes.route_finder.a_star_search", return_value=None):
        response = client.get("/optimized-route", params={
            "start_lat": 37.7749,
            "start_lon": -122.4194,
            "end_lat": 37.7849,
            "end_lon": -122.4074
        })
        assert response.status_code == 404
        print(f"\033[91m✗ No optimal route found (A* returned None) — as expected\033[0m")