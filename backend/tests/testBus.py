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
from app.router.bus import *

def print_header(text: str):
    print(f"\n{Fore.CYAN}=== {text} ==={Style.RESET_ALL}")

def print_stop_info(stop: dict):
    print(f"\n{Fore.YELLOW}🚏 Stop:{Style.RESET_ALL} {stop['stop_name']}")
    print(f"{Fore.YELLOW}📍 ID:{Style.RESET_ALL} {stop['stop_id']}")
    print(f"{Fore.YELLOW}📏 Distance:{Style.RESET_ALL} {stop['distance_miles']} miles")

def print_bus_info(bus: dict):
    status_color = Fore.GREEN if bus['status'] == 'On Time' else Fore.RED
    print(f"- {Fore.BLUE}Route {bus['route_number']}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}⏰ Arrival:{Style.RESET_ALL} {bus['arrival_time']}")
    print(f"  {status_color}⌚ Status:{Style.RESET_ALL} {bus['status']}")
    print(f"  {Fore.YELLOW}🏁 Destination:{Style.RESET_ALL} {bus['destination']}")

async def test_bus_service():
    bus_service = BusService()
    
    # Print GTFS paths
    print(f"BART GTFS Path: {bus_service.bart_gtfs_path}")
    print(f"Muni GTFS Path: {bus_service.muni_gtfs_path}")
    print()
    
    print("=== Testing Bus Service for location: 37.7729361, -122.4966348 ===\n")
    print("=== Finding nearby stops ===\n")
    
    nearby_buses = await bus_service.get_nearby_buses(37.7729361, -122.4966348, radius_miles=0.1)
    
    if nearby_buses:
        print(f"✓ Found {len(nearby_buses)} nearby stops\n")
        print(f"✓ Found buses for {len(nearby_buses)} stops\n")
        
        for stop_id, stop_info in nearby_buses.items():
            print(f"🚏 Stop: {stop_info['stop_name']}")
            print(f"📍 ID: {stop_id}")
            print(f"📏 Distance: {stop_info['distance_miles']} miles\n")
            
            schedule = stop_info['schedule']
            
            if schedule.get('outbound'):
                print("↗ Next Outbound Buses:")
                for bus in schedule['outbound']:
                    print(f"- Route {bus['route_number']}")
                    print(f"  ⏰ Arrival: {bus['arrival_time']}")
                    print(f"  ⌚ Status: {bus['status']}")
                    print(f"  🏁 Destination: {bus['destination']}")
                print()
                
            if schedule.get('inbound'):
                print("↙ Next Inbound Buses:")
                for bus in schedule['inbound']:
                    print(f"- Route {bus['route_number']}")
                    print(f"  ⏰ Arrival: {bus['arrival_time']}")
                    print(f"  ⌚ Status: {bus['status']}")
                    print(f"  🏁 Destination: {bus['destination']}")
                print()
    else:
        print("✗ No nearby stops found")

if __name__ == "__main__":
    asyncio.run(test_bus_service())