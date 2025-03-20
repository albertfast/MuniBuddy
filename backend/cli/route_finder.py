import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from app.route_finder2 import find_nearest_stop, find_route, get_live_bus_positions
from app.database import SessionLocal
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from sqlalchemy import text
import logging
from geopy.distance import great_circle

console = Console()

# logging setups
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_coordinates(address):
    """Find coordinates for an address."""
    try:
        geolocator = Nominatim(user_agent="munibuddy")
        location = geolocator.geocode(address + ", San Francisco, CA")  # Add city context
        if location:
            return location.latitude, location.longitude
        return None
    except GeocoderTimedOut:
        logger.error(f"Address not found: {address}")
        return None

def get_stop_details(stop_id, db):
    """Get stop details."""
    query = text("""
        SELECT stop_name, stop_lat, stop_lon
        FROM stops
        WHERE stop_id = :stop_id;
    """)
    result = db.execute(query, {"stop_id": stop_id}).fetchone()
    return result

def get_route_instructions(path, db):
    """Create route instructions."""
    instructions = []
    current_route = None
    
    # Find buses for each stop
    bus_query = text("""
        WITH route_stops AS (
            SELECT DISTINCT t.route_id, st.stop_id
            FROM stop_times st
            JOIN trips t ON st.trip_id = t.trip_id
            WHERE st.stop_id = ANY(:path)
        )
        SELECT DISTINCT r.route_id, r.route_type
        FROM routes r
        JOIN route_stops rs ON r.route_id = rs.route_id
        WHERE rs.stop_id = :stop_id;
    """)
    
    for i in range(len(path)-1):
        current_stop = path[i]
        next_stop = path[i+1]
        
        # Find buses passing through current stop
        buses = db.execute(bus_query, {"stop_id": current_stop, "path": path}).fetchall()
        next_buses = db.execute(bus_query, {"stop_id": next_stop, "path": path}).fetchall()
        
        # Find common routes
        common_routes = set(bus.route_id for bus in buses) & set(bus.route_id for bus in next_buses)
        
        if common_routes:
            # If continuing on same bus, skip
            if current_route in common_routes:
                continue
            
            # Taking a new bus
            current_route = list(common_routes)[0]
            current_route_type = next(bus.route_type for bus in buses if bus.route_id == current_route)
            
            # Get stop details
            current_stop_details = get_stop_details(current_stop, db)
            next_stop_details = get_stop_details(next_stop, db)
            
            if i == 0:
                instructions.append(f"🚌 Take {current_route} ({current_route_type}) bus from {current_stop_details[0]}")
                instructions.append(f"   📍 Stop Code: {current_stop}")
            else:
                instructions.append(f"🔄 Transfer to {current_route} ({current_route_type}) bus at {current_stop_details[0]}")
                instructions.append(f"   📍 Stop Code: {current_stop}")
    
    # Add instruction to get off at last stop
    if current_route:
        last_stop_details = get_stop_details(path[-1], db)
        if last_stop_details:
            instructions.append(f"🚶 Get off at {last_stop_details[0]}")
            instructions.append(f"   📍 Stop Code: {path[-1]}")
    
    return instructions

def main():
    console.print(Panel("""
[bold cyan]MuniBuddy Route Finder[/bold cyan]
The easiest way to find transit routes in San Francisco!
    """, title="🚌 Welcome to MuniBuddy"))
    
    while True:
        try:
            # Get start address
            start_address = console.input("\n[bold green]Where would you like to start?[/bold green] (default: 851 34th ave) ") or "851 34th ave"
            if start_address.lower() in ['q', 'quit', 'exit']:
                break
                
            # Get end address
            end_address = console.input("[bold green]Where would you like to go?[/bold green] (default: 520 mason st) ") or "520 mason st"
            if end_address.lower() in ['q', 'quit', 'exit']:
                break
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Finding route...", total=None)
                
                db = SessionLocal()
                try:
                    # Convert addresses to coordinates
                    start_coords = get_coordinates(start_address)
                    end_coords = get_coordinates(end_address)
                    
                    if not start_coords or not end_coords:
                        console.print("[red]❌ Addresses not found! Please try again.")
                        continue
                    
                    # Find nearest stops
                    start_stop = find_nearest_stop(start_coords[0], start_coords[1], db)
                    end_stop = find_nearest_stop(end_coords[0], end_coords[1], db)
                    
                    if not start_stop or not end_stop:
                        console.print("[red]❌ No nearby stops found! Please try another address.")
                        continue
                    
                    # Show route information
                    console.print(Panel(f"""
[green]Start:[/green] {start_stop['stop_name']} ({start_stop['stop_id']})
[green]End:[/green] {end_stop['stop_name']} ({end_stop['stop_id']})
                    """, title="📍 Stop Information"))
                    
                    # Find route
                    path = find_route(start_stop, end_stop, db)
                    if path:
                        # Create route instructions
                        instructions = get_route_instructions(path, db)
                        
                        # Show instructions
                        console.print(Panel("\n".join(instructions), title="🗺️ Route Instructions"))
                        
                        # Show stop details
                        table = Table(title="🚌 Stop Details")
                        table.add_column("Stop", style="cyan")
                        table.add_column("Stop Name", style="green")
                        table.add_column("Distance (mi)", style="yellow", justify="right")
                        
                        prev_stop = None
                        total_distance = 0
                        
                        for stop_id in path:
                            stop_details = get_stop_details(stop_id, db)
                            if stop_details:
                                if prev_stop:
                                    # Calculate distance between consecutive stops
                                    segment_distance = great_circle(
                                        (prev_stop[1], prev_stop[2]),  # lat, lon of previous stop
                                        (stop_details[1], stop_details[2])  # lat, lon of current stop
                                    ).miles
                                    total_distance += segment_distance
                                    table.add_row(
                                        str(stop_id),
                                        stop_details[0],
                                        f"{segment_distance:.2f}"
                                    )
                                else:
                                    table.add_row(
                                        str(stop_id),
                                        stop_details[0],
                                        "0.00"
                                    )
                                prev_stop = stop_details
                        
                        console.print(table)
                        console.print(f"\n[green]Total distance:[/green] {total_distance:.2f} miles")
                    else:
                        console.print("[red]❌ No route found! Please try another address.")
                    
                except Exception as e:
                    console.print(f"[red]❌ Error: {str(e)}")
                finally:
                    db.close()
            
            # Ask if want to continue
            if console.input("\n[cyan]Would you like to search for another route? (Y/N): [/cyan]").lower() != 'y':
                break
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Program terminated.[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]❌ Error: {str(e)}")
            continue

if __name__ == "__main__":
    main()