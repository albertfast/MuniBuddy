import os
import sys
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama for colored output
init()

# Change working directory to backend folder
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add project root to Python path
sys.path.insert(0, os.getcwd())

import asyncio
from app.services.bus_service import BusService

def print_header(text: str):
    print(f"\n{Fore.CYAN}=== {text} ==={Style.RESET_ALL}")

def print_stop_info(stop: dict):
    try:
        print(f"\n{Fore.YELLOW}🚏 Stop:{Style.RESET_ALL} {stop.get('stop_name', 'Unknown')}")
        print(f"{Fore.YELLOW}📍 ID:{Style.RESET_ALL} {stop.get('id', 'Unknown')}")
        print(f"{Fore.YELLOW}📏 Distance:{Style.RESET_ALL} {stop.get('distance_miles', 'Unknown')} miles")
    except Exception as e:
        print(f"{Fore.RED}Error printing stop info: {str(e)}{Style.RESET_ALL}")

def print_bus_info(bus: dict):
    try:
        status_color = Fore.GREEN if bus.get('status') == 'On Time' else Fore.RED
        print(f"- {Fore.BLUE}Route {bus.get('route_number', 'Unknown')}{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}⏰ Arrival:{Style.RESET_ALL} {bus.get('arrival_time', 'Unknown')}")
        print(f"  {status_color}⌚ Status:{Style.RESET_ALL} {bus.get('status', 'Unknown')}")
        print(f"  {Fore.YELLOW}🏁 Destination:{Style.RESET_ALL} {bus.get('destination', 'Unknown')}")
    except Exception as e:
        print(f"{Fore.RED}Error printing bus info: {str(e)}{Style.RESET_ALL}")

async def test_bus_service():
    bus_service = BusService()
    
    # Print GTFS paths
    print(f"BART GTFS Path: {bus_service.bart_gtfs_path}")
    print(f"Muni GTFS Path: {bus_service.muni_gtfs_path}")
    print()
    
    # Test locations with larger radius
    test_locations = [
        {
            "name": "City College of San Francisco",
            "lat": 37.7257,
            "lon": -122.4511,
            "radius": 0.5  # Increased radius
        },
        {
            "name": "Golden Gate Park",
            "lat": 37.7694,
            "lon": -122.4862,
            "radius": 0.5
        },
        {
            "name": "Fisherman's Wharf",
            "lat": 37.8097,
            "lon": -122.4098,
            "radius": 0.5
        },
        {
            "name": "Mission District",
            "lat": 37.7599,
            "lon": -122.4148,
            "radius": 0.5
        },
        {
            "name": "Ocean Beach",
            "lat": 37.7599,
            "lon": -122.5118,
            "radius": 0.5
        }
    ]
    
    for location in test_locations:
        try:
            print_header(f"Testing location: {location['name']}")
            print(f"Coordinates: {location['lat']}, {location['lon']}")
            print(f"Search radius: {location['radius']} miles\n")
            
            nearby_buses = await bus_service.get_nearby_buses(
                location['lat'], 
                location['lon'], 
                radius_miles=location['radius']
            )
            
            if nearby_buses:
                print(f"✓ Found {len(nearby_buses)} nearby stops\n")
                print(f"✓ Found buses for {len(nearby_buses)} stops\n")
                
                for stop_id, stop_info in nearby_buses.items():
                    print_stop_info(stop_info)
                    schedule = stop_info.get('schedule', {})
                    
                    if schedule.get('outbound'):
                        print(f"{Fore.CYAN}↗ Next Outbound Buses:{Style.RESET_ALL}")
                        for bus in schedule['outbound']:
                            print_bus_info(bus)
                        print()
                        
                    if schedule.get('inbound'):
                        print(f"{Fore.CYAN}↙ Next Inbound Buses:{Style.RESET_ALL}")
                        for bus in schedule['inbound']:
                            print_bus_info(bus)
                        print()
            else:
                print(f"{Fore.RED}✗ No nearby stops found{Style.RESET_ALL}")
            
            print(f"{Fore.GREEN}{'='*50}{Style.RESET_ALL}\n")
            
        except Exception as e:
            print(f"{Fore.RED}Error testing location {location['name']}: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{'='*50}{Style.RESET_ALL}\n")

if __name__ == "__main__":
    asyncio.run(test_bus_service())