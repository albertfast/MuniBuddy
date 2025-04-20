import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from app.services.bart_service import BartService
from app.services.schedule_service import SchedulerService

# Mock coordinates around Powell BART
LAT, LON = 37.7843, -122.4078

@pytest.fixture
def bart_service():
    scheduler = SchedulerService()
    return BartService(scheduler)

def test_get_nearby_barts(bart_service):
    nearby = bart_service.get_nearby_barts(LAT, LON, radius=0.2)
    assert isinstance(nearby, list)
    assert all('stop_id' in stop for stop in nearby)
    assert any('powell' in stop['stop_name'].lower() for stop in nearby)

@pytest.mark.asyncio
async def test_get_stop_predictions(bart_service):
    results = await bart_service.get_stop_predictions("POWL")
    assert 'inbound' in results
    assert 'outbound' in results
    assert isinstance(results["inbound"], list)
    assert isinstance(results["outbound"], list)
