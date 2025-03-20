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
from app.services.scheduler_service import SchedulerService

async def test_scheduler_service():
    scheduler = SchedulerService()
    
    # Test schedule retrieval
    try:
        schedule = await scheduler.get_schedule("4211")  # Fulton St & 33rd Ave
        if schedule:
            print("\n=== Schedule for Fulton St & 33rd Ave ===\n")
            
            if schedule.get('outbound'):
                print("↗ Outbound Buses:")
                for bus in schedule['outbound']:
                    print(f"- Route {bus['route_number']}")
                    print(f"  ⏰ Arrival: {bus['arrival_time']}")
                    print(f"  ⌚ Status: {bus['status']}")
                    print(f"  🏁 Destination: {bus['destination']}")
                print()
            
            if schedule.get('inbound'):
                print("↙ Inbound Buses:")
                for bus in schedule['inbound']:
                    print(f"- Route {bus['route_number']}")
                    print(f"  ⏰ Arrival: {bus['arrival_time']}")
                    print(f"  ⌚ Status: {bus['status']}")
                    print(f"  🏁 Destination: {bus['destination']}")
                print()
        else:
            print("✗ No schedule data available")
            
    except Exception as e:
        print(f"✗ Error testing scheduler service: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_scheduler_service())