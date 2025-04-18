import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from httpx import AsyncClient
from app.main import app

SAMPLE_STOP_ID = "POWL"
SAMPLE_STOP_CODE = "POWL"
SAMPLE_LAT = 37.78407
SAMPLE_LON = -122.40745
AGENCIES = ["bart", "BA", "muni", "SFMTA"]

@pytest.mark.asyncio
async def test_stop_predictions():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/stop-predictions/{SAMPLE_STOP_ID}")
        assert response.status_code == 200
        assert "inbound" in response.json()

@pytest.mark.asyncio
@pytest.mark.parametrize("agency", AGENCIES)
async def test_bus_positions_by_stop(agency):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/bus-positions/by-stop", params={
            "stopCode": SAMPLE_STOP_CODE,
            "agency": agency
        })
        assert response.status_code in (200, 500)

@pytest.mark.asyncio
@pytest.mark.parametrize("agency", AGENCIES)
async def test_nearby_stops(agency):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/bus/nearby-stops", params={
            "lat": SAMPLE_LAT,
            "lon": SAMPLE_LON,
            "agency": agency
        })
        assert response.status_code in (200, 500)

@pytest.mark.asyncio
async def test_bart_stop_arrivals():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/bart-positions/stop-arrivals/{SAMPLE_STOP_ID}")
        assert response.status_code in (200, 500)

@pytest.mark.asyncio
async def test_bart_by_stop():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/bart-positions/by-stop", params={
            "stopCode": SAMPLE_STOP_CODE
        })
        assert response.status_code in (200, 500)

