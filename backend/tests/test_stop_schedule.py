import sys
from pathlib import Path

# Add the backend directory to the Python module search path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.router.stop_schedule import router
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI

# Create a FastAPI app and include the router
app = FastAPI()
app.include_router(router)

client = TestClient(app)

@patch("app.core.singleton.bus_service.fetch_real_time_stop_data")
@patch("app.core.singleton.bus_service.get_stop_schedule")
def test_get_stop_schedule_real_time(mock_get_stop_schedule, mock_fetch_real_time_stop_data):
    # Mock real-time data response
    mock_fetch_real_time_stop_data.return_value = {
        "inbound": [{"bus": "1", "arrival": "10:00"}],
        "outbound": []
    }
    mock_get_stop_schedule.return_value = {}

    # Make a request to the endpoint
    response = client.get("/stop-schedule/test-stop-id")

    # Assert the response
    assert response.status_code == 200
    assert response.json() == {
        "inbound": [{"bus": "1", "arrival": "10:00"}],
        "outbound": []
    }

@patch("app.core.singleton.bus_service.fetch_real_time_stop_data")
@patch("app.core.singleton.bus_service.get_stop_schedule")
def test_get_stop_schedule_fallback(mock_get_stop_schedule, mock_fetch_real_time_stop_data):
    # Mock no real-time data and fallback to static schedule
    mock_fetch_real_time_stop_data.return_value = {}
    mock_get_stop_schedule.return_value = {
        "static_schedule": [{"bus": "2", "arrival": "11:00"}]
    }

    # Make a request to the endpoint
    response = client.get("/stop-schedule/test-stop-id")

    # Assert the response
    assert response.status_code == 200
    assert response.json() == {
        "static_schedule": [{"bus": "2", "arrival": "11:00"}]
    }

@patch("app.core.singleton.bus_service.fetch_real_time_stop_data")
@patch("app.core.singleton.bus_service.get_stop_schedule")
def test_get_stop_schedule_error(mock_get_stop_schedule, mock_fetch_real_time_stop_data):
    # Mock an exception in the service
    mock_fetch_real_time_stop_data.side_effect = Exception("Service error")

    # Make a request to the endpoint
    response = client.get("/stop-schedule/test-stop-id")

    # Assert the response
    assert response.status_code == 500
    assert response.json() == {"detail": "Schedule fetch failed: Service error"}
