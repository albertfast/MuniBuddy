# Add parent directory to path
# import os
# import sys
# sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from app.db.database import get_db
# from app.models.bus_route import BusRoute

# router = APIRouter()

# @router.get("/arrival-time")
# def get_arrival_time(db: Session = Depends(get_db)):
#     """Fetch scheduled arrival times."""
#     return db.query(BusRoute).all()


# from fastapi import APIRouter, HTTPException, Query
# import requests
# from app.config import API_KEY
# from app.services.scheduler_service import get_best_bus_for_arrival

# # Create router with a prefix for better organization
# router = APIRouter(prefix="/arrival", tags=["Arrival Time"])

# @router.get("/calculate")
# def get_arrival_time(destination: str, arrival_time: str):
#     """
#     Determines the best bus option to reach the given destination by a specific arrival time.
#     Queries the 511 SF Bay API for real-time bus schedules.
#     """
    
#     # Ensure API key is available
#     if not API_KEY:
#         raise HTTPException(status_code=500, detail="API_KEY is not defined in environment variables")

#     # Construct API request URL for bus tracking data
#     api_url = f"http://api.511.org/transit/StopMonitoring?api_key={API_KEY}&format=json"
    
#     try:
#         response = requests.get(api_url)
#         response.raise_for_status()  # Raise an HTTP error for non-200 responses
#     except requests.exceptions.RequestException as e:
#         raise HTTPException(status_code=500, detail=f"Error fetching data from API: {str(e)}")

#     # Parse the response as JSON
#     try:
#         data = response.json()
#     except ValueError:
#         raise HTTPException(status_code=500, detail="Failed to parse JSON response from 511 API")

#     # Debug log: check API response structure
#     if "ServiceDelivery" not in data:
#         raise HTTPException(status_code=500, detail="Invalid response format from API")

#     # Find the best bus using the scheduler service
#     best_bus = get_best_bus_for_arrival(destination, arrival_time, data)

#     # Handle case where no valid bus is found
#     if not best_bus:
#         raise HTTPException(status_code=404, detail="No suitable bus found for the requested arrival time")

#     # Return detailed response with best bus information
#     return {
#         "message": "Best bus found for arrival time",
#         "bus_number": best_bus["LineRef"],
#         "published_name": best_bus.get("PublishedLineName", "Unknown"),
#         "current_stop": best_bus.get("OriginName", "Unknown"),
#         "destination": best_bus.get("DestinationName", "Unknown"),
#         "expected_arrival": best_bus["MonitoredCall"]["ExpectedArrivalTime"],
#         "vehicle_id": best_bus.get("VehicleRef", "N/A")
#     }

# @router.get("/estimate-arrival")
# def estimate_arrival(bus_number: str, stop_name: str = Query(None, description="Name of the stop to estimate arrival time")):
#     """
#     Estimates the arrival time of a specific bus at a given stop.
#     If no stop is provided, it returns general information about the bus.
#     """
    
#     # Ensure API key is available
#     if not API_KEY:
#         raise HTTPException(status_code=500, detail="API_KEY is not defined in environment variables")

#     # Construct API request URL
#     api_url = f"http://api.511.org/transit/StopMonitoring?api_key={API_KEY}&format=json"

#     try:
#         response = requests.get(api_url)
#         response.raise_for_status()
#         data = response.json()
#     except requests.exceptions.RequestException as e:
#         raise HTTPException(status_code=500, detail=f"Error fetching data from API: {str(e)}")

#     # Debug log: check API response structure
#     if "ServiceDelivery" not in data:
#         raise HTTPException(status_code=500, detail="Invalid response format from API")

#     estimated_time = None
#     for stop in data["ServiceDelivery"]["StopMonitoringDelivery"]["MonitoredStopVisit"]:
#         bus_info = stop["MonitoredVehicleJourney"]
        
#         # Check if this is the correct bus number
#         if bus_info["LineRef"] == bus_number:
#             if stop_name and bus_info["MonitoredCall"]["StopPointName"] != stop_name:
#                 continue  # Skip if stop name is provided but does not match
            
#             estimated_time = bus_info["MonitoredCall"]["ExpectedArrivalTime"]
#             break

#     if not estimated_time:
#         raise HTTPException(status_code=404, detail=f"No arrival data found for bus {bus_number} at stop {stop_name if stop_name else 'any'}.")

#     return {
#         "message": f"Estimated arrival time for bus {bus_number} at stop {stop_name if stop_name else 'any'}",
#         "expected_arrival": estimated_time
#     }

