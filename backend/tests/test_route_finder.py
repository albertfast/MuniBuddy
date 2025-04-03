import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import json
import os
import sys

# Change working directory to backend folder
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

from app.main import app

client = TestClient(app)
mock_route = ["stop_123", "stop_456", "stop_789"]


@pytest.fixture(autouse=True)
def patch_dependencies():
    with patch("app.route_finder.redis") as mock_redis, \
         patch("app.route_finder.get_live_bus_positions") as mock_live, \
         patch("app.route_finder.find_nearest_stop") as mock_nearest, \
         patch("app.route_finder.a_star_search") as mock_astar:

        mock_redis.get.return_value = None
        mock_redis.setex = MagicMock()

        mock_nearest.side_effect = [
            {"stop_id": "start_001", "lat": 37.7749, "lon": -122.4194},
            {"stop_id": "end_001", "lat": 37.7849, "lon": -122.4074}
        ]

        mock_live.return_value = [{"vehicle_id": "bus_01"}]
        mock_astar.return_value = mock_route

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


def test_missing_nearby_stop():
    with patch("app.route_finder.find_nearest_stop", side_effect=[None, None]):
        response = client.get("/optimized-route", params={
            "start_lat": 0.0,
            "start_lon": 0.0,
            "end_lat": 0.0,
            "end_lon": 0.0
        })
        assert response.status_code == 404
        print(f"\033[93m⚠️ No nearby start or end stop found\033[0m")


def test_live_data_failure():
    with patch("app.route_finder.get_live_bus_positions", return_value=None):
        response = client.get("/optimized-route", params={
            "start_lat": 37.7749,
            "start_lon": -122.4194,
            "end_lat": 37.7849,
            "end_lon": -122.4074
        })
        assert response.status_code == 500
        print(f"\033[91m✗ Live bus data unavailable — gracefully handled\033[0m")


def test_route_caching():
    with patch("app.route_finder.redis.get", return_value=json.dumps(mock_route)):
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
    with patch("app.route_finder.a_star_search", return_value=None):
        response = client.get("/optimized-route", params={
            "start_lat": 37.7749,
            "start_lon": -122.4194,
            "end_lat": 37.7849,
            "end_lon": -122.4074
        })
        assert response.status_code == 404
        print(f"\033[91m✗ No optimal route found (A* returned None) — as expected\033[0m")
