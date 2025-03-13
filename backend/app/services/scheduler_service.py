def calculate_optimal_bus(arrival_time, schedule_data):
    """Finds the best bus option for a given arrival time."""
    best_bus = None
    for schedule in schedule_data:
        if schedule.arrival_time <= arrival_time:
            best_bus = schedule
    return best_bus


# import requests
# from app.config import API_KEY

# def get_best_bus_for_arrival(destination: str, arrival_time: str):
#     """
#     Fetches buses and determines the best option based on the user's required arrival time.
#     """
#     api_url = f"http://api.511.org/transit/StopMonitoring?api_key={API_KEY}&format=json"
#     response = requests.get(api_url)

#     if response.status_code != 200:
#         raise Exception(f"Error fetching data from API: {response.status_code}")

#     data = response.json()

#     # Select the best bus based on expected arrival time
#     best_bus = None
#     for stop in data["ServiceDelivery"]["StopMonitoringDelivery"]["MonitoredStopVisit"]:
#         bus_info = stop["MonitoredVehicleJourney"]
#         expected_arrival = bus_info["MonitoredCall"]["ExpectedArrivalTime"]

#         if expected_arrival and expected_arrival <= arrival_time:
#             best_bus = bus_info
#             break

#     if not best_bus:
#         return None  # No bus found

#     return {
#         "bus_number": best_bus["LineRef"],
#         "current_stop": best_bus["OriginName"],
#         "destination": best_bus["DestinationName"],
#         "expected_arrival": best_bus["MonitoredCall"]["ExpectedArrivalTime"]
#     }
