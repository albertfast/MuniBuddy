from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.bus_route import BusRoute

router = APIRouter()

@router.get("/routes")
def get_routes(db: Session = Depends(get_db)):
    """Fetch all bus routes from the database."""
    return db.query(BusRoute).all()

@router.get("/bus-positions")
def get_bus_positions(bus_number: str, agency: str):
    """Returns real-time bus positions."""
    return {"bus_number": bus_number, "agency": agency}

# ...existing imports and setup code...

@app.get("/get-route-details")
def get_route_details(route_short_name: str = Query(None, description="Bus route short name")):
    """
    Fetch route details from GTFS file using `route_short_name`.
    If route is not found in GTFS, it attempts to fetch from 511 API.
    """
    try:
        # 📌 Read GTFS routes.txt file
        routes_file = "gtfs_data/routes.txt"
        routes_df = pd.read_csv(routes_file, dtype=str)  # Read all data as string

        # 🔍 Query GTFS file with `route_short_name`
        route_info = routes_df[routes_df["route_short_name"] == route_short_name]

        # 📌 If route exists in GTFS file, return as JSON
        if not route_info.empty:
            route_details = route_info.to_dict(orient="records")[0]

            # 🚨 Check for invalid float values in JSON
            for key, value in route_details.items():
                if isinstance(value, float) and (pd.isna(value) or value == float("inf") or value == float("-inf")):
                    route_details[key] = None  # Make JSON compatible

            return {"route_details": route_details}

        # 🚨 If not found in GTFS, make request to 511 API
        API_URL = f"{BASE_API_URL}/RouteDetails?api_key={API_KEY}&agency={AGENCY_ID}&route_id={route_short_name}&format=json"
        response = requests.get(API_URL)

        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Route not found in GTFS data or 511 API")

        # Process 511 API response
        try:
            cleaned_text = response.text.lstrip("\ufeff")
            data = json.loads(cleaned_text)
            if isinstance(data, dict) and "RouteInfo" in data:
                return {"route_details": data["RouteInfo"]}
            return {"error": "Route details not found", "data": data}
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail=f"Invalid JSON response: {cleaned_text[:500]}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading GTFS data: {str(e)}")


# from fastapi import APIRouter, HTTPException, Query, FastAPI
# import requests
# import xml.etree.ElementTree as ET
# import pandas as pd
# import os
# import json
# from app.services.bus_service import get_live_bus_positions, get_all_gtfs_routes, get_gtfs_route_details
# from typing import Optional
# from app.services.gtfs_service import load_gtfs_data  # Import GTFS data loader
# from app.config import API_KEY, AGENCY_ID,  DATABASE_URL # Ensure API_KEY is properly loaded
# from sqlalchemy.orm import Session
# from app.database import SessionLocal
# from app.models import BusRoute

# GTFS_DIR = "gtfs_data"
# # Initialize FastAPI app
# app = FastAPI()

# # 511 API Base URL
# BASE_API_URL = "http://api.511.org/transit"
# # Initialize FastAPI router for bus-related endpoints
# router = APIRouter(prefix="/bus", tags=["Bus"])

# def parse_xml_response(xml_text):
#     """
#     Parses XML response from the 511 API and converts it into structured JSON.
#     Handles missing or incorrect data and logs any parsing issues.
#     """
#     namespaces = {'siri': 'http://www.siri.org.uk/siri'}
#     try:
#         root = ET.fromstring(xml_text)
#     except ET.ParseError as e:
#         raise HTTPException(status_code=500, detail=f"XML Parse Error: {str(e)}")
    
#     bus_positions = []
#     for monitored in root.findall(".//siri:MonitoredVehicleJourney", namespaces):
#         try:
#             # Validate Latitude/Longitude data to avoid errors
#             lat_elem = monitored.find("siri:VehicleLocation/siri:Latitude", namespaces)
#             lon_elem = monitored.find("siri:VehicleLocation/siri:Longitude", namespaces)
#             if lat_elem is None or lon_elem is None:
#                 continue  # Skip entry if coordinates are missing
            
#             latitude = float(lat_elem.text)
#             longitude = float(lon_elem.text)
            
#             bus_data = {
#                 "bus_number": monitored.find("siri:LineRef", namespaces).text,
#                 "published_name": monitored.find("siri:PublishedLineName", namespaces).text,
#                 "current_stop": monitored.find(".//siri:StopPointName", namespaces).text,
#                 "latitude": latitude,
#                 "longitude": longitude,
#                 "arrival_time": monitored.find(".//siri:ExpectedArrivalTime", namespaces).text,
#                 "destination": monitored.find("siri:DestinationName", namespaces).text
#             }
#             bus_positions.append(bus_data)
#         except (AttributeError, ValueError) as e:
#             print(f"Warning: Skipping entry due to missing data or parsing issue: {str(e)}")
#             continue  # Skip invalid entries
    
#     return bus_positions

# @router.get("/bus-positions")
# def get_bus_positions(bus_number: str, agency: str = "SF"):
#     """
#     Fetch real-time bus positions for a specific agency and bus number.
#     Converts XML response to JSON and validates with GTFS data.
#     """
#     if not API_KEY:
#         raise HTTPException(status_code=500, detail="API_KEY is not set in config.")
    
#     # Construct API request URL
#     api_url = f"http://api.511.org/transit/StopMonitoring?api_key={API_KEY}&agency={agency}&format=xml"
#     response = requests.get(api_url)
    
#     if response.status_code != 200:
#         raise HTTPException(status_code=500, detail=f"Error fetching data from API: {response.status_code}")
    
#     # Parse XML response from 511 API
#     bus_positions = parse_xml_response(response.text)
    
#     # Load GTFS data
#     try:
#         routes_df, trips_df, stops_df = load_gtfs_data()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error loading GTFS data: {str(e)}")
    
#     # Validate bus routes with GTFS route data
#     matched_buses = [
#         bus for bus in bus_positions if bus["bus_number"] in routes_df["route_short_name"].values
#     ]
    
#     if not matched_buses:
#         raise HTTPException(status_code=404, detail=f"Bus route {bus_number} not found in GTFS data")
    
#     return {"bus_positions": matched_buses}

# @router.get("/get-all-routes")
# async def get_all_routes():
#     """Fetches all available bus routes from GTFS."""
#     try:
#         all_routes = get_all_gtfs_routes()
#         return {"routes": all_routes}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error reading GTFS data: {e}")

# @app.get("/get-route-details")
# def get_route_details(route_short_name: str = Query(None, description="Bus route short name")):
#     """
#     Fetch route details from GTFS file using `route_short_name`.
#     If route is not found in GTFS, it attempts to fetch from 511 API.
#     """
#     try:
#         # 📌 GTFS routes.txt dosyasını oku
#         routes_file = "gtfs_data/routes.txt"
#         routes_df = pd.read_csv(routes_file, dtype=str)  # Tüm verileri string olarak oku

#         # 🔍 `route_short_name` ile GTFS dosyasını sorgula
#         route_info = routes_df[routes_df["route_short_name"] == route_short_name]

#         # 📌 Eğer GTFS dosyasında ilgili rota varsa JSON olarak dön
#         if not route_info.empty:
#             route_details = route_info.to_dict(orient="records")[0]

#             # 🚨 JSON'da geçersiz float değerleri kontrol et
#             for key, value in route_details.items():
#                 if isinstance(value, float) and (pd.isna(value) or value == float("inf") or value == float("-inf")):
#                     route_details[key] = None  # JSON uyumlu hale getir

#             return {"route_details": route_details}

#         # 🚨 Eğer GTFS'de bulunmazsa 511 APIye istek yap
#         API_URL = f"{BASE_API_URL}/RouteDetails?api_key={API_KEY}&agency={AGENCY_ID}&route_id={route_short_name}&format=json"
#         response = requests.get(API_URL)

#         if response.status_code == 404:
#             raise HTTPException(status_code=404, detail="Route not found in GTFS data or 511 API")

#         # 511 API yanıtını işle
#         try:
#             cleaned_text = response.text.lstrip("\ufeff")
#             data = json.loads(cleaned_text)
#             if isinstance(data, dict) and "RouteInfo" in data:
#                 return {"route_details": data["RouteInfo"]}
#             return {"error": "Route details not found", "data": data}
#         except json.JSONDecodeError:
#             raise HTTPException(status_code=500, detail=f"Invalid JSON response: {cleaned_text[:500]}")

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error reading GTFS data: {str(e)}")