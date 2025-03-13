from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import requests
import json
import xmltodict
import xml.etree.ElementTree as ET
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models.bus_route import BusRoute
from .config import API_KEY, AGENCY_ID, DATABASE_URL
import math

# Initialize FastAPI application
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to ["http://127.0.0.1:5500"] for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables from .env file
load_dotenv()
# 🌍 Read environment variables
API_KEY = os.getenv("API_KEY")
AGENCY_ID = os.getenv("AGENCY_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

# ❌ Raise error if variables are not loaded
if not API_KEY:
    raise ValueError("🚨 API_KEY is not set in the .env file!")
if not AGENCY_ID:
    raise ValueError("🚨 AGENCY_ID is not set in the .env file!")
if not DATABASE_URL:
    raise ValueError("🚨 DATABASE_URL is not set in the .env file!")

GTFS_DIR = "gtfs_data"

# Initialize FastAPI application
app = FastAPI()

# Base URL for 511 API
BASE_API_URL = "http://api.511.org/transit"

@app.get("/")
def home():
    return {"message": "MuniBuddy API is running!"}


def load_gtfs_data():
    """Loads GTFS route data from local GTFS files"""
    routes_file = os.path.join(GTFS_DIR, "routes.txt")
    return pd.read_csv(routes_file, dtype=str)

def clean_json_data(data):
    """Removes NaN, Infinity values from JSON to prevent conversion errors"""
    for key, value in data.items():
        if isinstance(value, float) and (math.isnan(value) or value == float("inf") or value == float("-inf")):
            data[key] = None  # Replace invalid float values with None
    return data

def fetch_live_bus_positions(agency):
    """Fetches live bus positions from 511 API and converts XML to JSON if necessary."""
    API_URL = f"http://api.511.org/transit/VehicleMonitoring?api_key={API_KEY}&agency={agency}"

    response = requests.get(API_URL)

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="511 API request failed with status 404 (Not Found)")

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"511 API request failed with status {response.status_code}")

    # ✅ Process as UTF-8 after cleaning BOM
    raw_text = response.content.decode("utf-8-sig").strip()
    print("📌 API Raw Response (First 500 chars):", raw_text[:500])  # Debug log

    try:
        # 🛑 If response is in JSON format, convert directly to JSON
        if response.headers.get("Content-Type", "").startswith("application/json"):
            return json.loads(raw_text)  # JSON format should be processed properly

        # 🛑 If response is in XML format, convert XML to JSON
        try:
            # Check if XML is valid
            ET.fromstring(raw_text)
        except ET.ParseError as e:
            raise HTTPException(status_code=500, detail=f"Invalid XML response: {str(e)}")

        # Convert XML to JSON
        data_dict = xmltodict.parse(raw_text)
        json_data = json.loads(json.dumps(data_dict))

        return json_data
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Error parsing JSON response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing API response: {str(e)}")

@app.get("/bus-positions")
def get_bus_positions(bus_number: str = Query(..., description="Bus number"), agency: str = Query(..., description="Transit agency")):
    """Fetches real-time bus positions from 511 API and matches them with GTFS route data."""

    # Load GTFS data
    routes_df = load_gtfs_data()
    
    # Fetch live bus positions
    live_data = fetch_live_bus_positions(agency)

    bus_positions = []
    vehicle_activities = live_data.get("Siri", {}).get("ServiceDelivery", {}).get("VehicleMonitoringDelivery", {}).get("VehicleActivity", [])

    if not isinstance(vehicle_activities, list):
        vehicle_activities = [vehicle_activities]  # Convert to list if it's a single object

    for vehicle in vehicle_activities:
        journey = vehicle.get("MonitoredVehicleJourney", {})

        # Extract required fields
        line_ref = journey.get("LineRef", "Unknown")
        operator_ref = journey.get("OperatorRef", "Unknown")

        if line_ref == bus_number and operator_ref == agency:
            matching_route = routes_df[routes_df["route_short_name"] == line_ref]
            route_name = matching_route.iloc[0]["route_long_name"] if not matching_route.empty else "Unknown"

            # Clean JSON data before returning
            bus_data = {
                "bus_number": line_ref,
                "route_name": route_name,
                "operator": operator_ref,
                "current_stop": journey.get("MonitoredCall", {}).get("StopPointName", "Unknown"),
                "latitude": journey.get("VehicleLocation", {}).get("Latitude", "Unknown"),
                "longitude": journey.get("VehicleLocation", {}).get("Longitude", "Unknown"),
                "arrival_time": journey.get("MonitoredCall", {}).get("ExpectedArrivalTime", "Unknown")
            }

            bus_positions.append(clean_json_data(bus_data))

    if not bus_positions:
        raise HTTPException(status_code=404, detail="Bus route not found in live data")

    return {"bus_positions": bus_positions}

@app.get("/get-route-details")
def get_route_details(route_short_name: str = Query(..., description="Bus route short name")):
    try:
        routes_file = "gtfs_data/routes.txt"
        routes_df = pd.read_csv(routes_file, dtype=str)
        route_info = routes_df[routes_df["route_short_name"] == route_short_name]

        if not route_info.empty:
            route_details = route_info.to_dict(orient="records")[0]
            route_details = clean_json_data(route_details)  # 🚨 Clean JSON format
            return {"route_details": route_details}

        # 🚨 If not found in GTFS, query from 511 API
        API_URL = f"http://api.511.org/transit/RouteDetails?api_key={API_KEY}&agency={AGENCY_ID}&route_id={route_short_name}&format=json"
        response = requests.get(API_URL)

        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Route not found in GTFS or 511 API")

        # Process JSON data after cleaning
        try:
            cleaned_text = response.text.lstrip("\ufeff")
            data = json.loads(cleaned_text)
            if isinstance(data, dict) and "RouteInfo" in data:
                return {"route_details": clean_json_data(data["RouteInfo"])}
            return {"error": "Route details not found", "data": data}
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail=f"Invalid JSON response: {cleaned_text[:500]}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading GTFS data: {str(e)}")