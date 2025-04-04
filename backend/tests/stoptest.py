import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Add the project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# IMPORTANT: Set up all patches BEFORE importing any application modules
# Create a proper async mock for the get_stop_schedule method
async def mock_get_schedule(*args, **kwargs):
    # This will be overridden in each test
    return {"inbound": [], "outbound": []}

# Create a mock bus service instance
mock_bus_service = MagicMock()
# Set up the async method
mock_bus_service.get_stop_schedule = AsyncMock(side_effect=mock_get_schedule)

# THIS IS THE KEY PART - patch at module level before import
bus_service_patch = patch('app.services.bus_service.BusService', return_value=mock_bus_service)
bus_service_patch.start()

# Also patch the constructor in the router module
router_bus_service_patch = patch('app.router.bus_service.BusService', return_value=mock_bus_service)
router_bus_service_patch.start()

# Now import the router after patching
from app.router.stop_schedule import router

# Create a FastAPI app for testing
app = FastAPI()
app.include_router(router)
client = TestClient(app)

# Define test data
sample_schedule = {
    "inbound": [
        {"route_number": "38", "destination": "Downtown", "arrival_time": "10:15 AM", "status": "On Time"},
        {"route_number": "38R", "destination": "Downtown", "arrival_time": "10:25 AM", "status": "Delayed (2 min)"}
    ],
    "outbound": [
        {"route_number": "38", "destination": "Ocean Beach", "arrival_time": "10:10 AM", "status": "On Time"},
        {"route_number": "38R", "destination": "Ocean Beach", "arrival_time": "10:22 AM", "status": "On Time"}
    ]
}

empty_schedule = {"inbound": [], "outbound": []}

@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks before each test"""
    mock_bus_service.reset_mock()
    mock_bus_service.get_stop_schedule.reset_mock()


def test_get_stop_schedule_success():
    """Test successful stop schedule retrieval"""
    # Configure mock to return sample schedule
    async def success_response(*args, **kwargs):
        return sample_schedule
    
    # Update the side_effect
    mock_bus_service.get_stop_schedule.side_effect = success_response
    
    # Call the endpoint
    response = client.get("/stop-schedule/4212")
    
    # Verify response
    assert response.status_code == 200
    assert response.json() == sample_schedule
    mock_bus_service.get_stop_schedule.assert_called_once_with("4212")


def test_get_stop_schedule_empty():
    """Test when no schedules are found"""
    # Configure mock to return empty schedule
    async def empty_response(*args, **kwargs):
        return empty_schedule
    
    mock_bus_service.get_stop_schedule.side_effect = empty_response
    
    # Call the endpoint
    response = client.get("/stop-schedule/unknown_stop")
    
    # Verify response (should still be 200 OK with empty data)
    assert response.status_code == 200
    assert response.json() == empty_schedule
    mock_bus_service.get_stop_schedule.assert_called_once_with("unknown_stop")


def test_get_stop_schedule_service_error():
    """Test when SchedulerService raises an exception"""
    # Configure mock to raise an exception
    async def error_response(*args, **kwargs):
        raise Exception("Service unavailable")
        
    mock_bus_service.get_stop_schedule.side_effect = error_response
    
    # Call the endpoint
    response = client.get("/stop-schedule/4212")
    
    # Verify response
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]
    mock_bus_service.get_stop_schedule.assert_called_once_with("4212")


def test_get_stop_schedule_http_exception():
    """Test when SchedulerService raises an HTTPException"""
    # Configure mock to raise an HTTPException
    async def http_error_response(*args, **kwargs):
        raise HTTPException(status_code=404, detail="Stop not found")
        
    mock_bus_service.get_stop_schedule.side_effect = http_error_response
    
    # Call the endpoint
    response = client.get("/stop-schedule/invalid")
    
    # Verify response (should propagate the status code and detail)
    assert response.status_code == 404
    assert response.json()["detail"] == "Stop not found"
    mock_bus_service.get_stop_schedule.assert_called_once_with("invalid")


def test_empty_stop_id():
    """Test with an empty stop ID"""
    response = client.get("/stop-schedule/")
    assert response.status_code == 404


# Clean up patches at the end of the test module
def teardown_module(module):
    """Cleanup function to stop all patches"""
    bus_service_patch.stop()
    router_bus_service_patch.stop()
