import requests
import json
from rich.console import Console
from rich.traceback import install
from rich.panel import Panel
from rich.syntax import Syntax
from app.db import get_db
from app.config import settings
from app.route_finder import *
from fastapi import FastAPI, APIRouter, Depends
from app.route_api import router as route_api_router
from app.router.bus import router as bus_router
from rich.table import Table

app = FastAPI()
router = APIRouter()

API_KEY = settings.API_KEY
AGENCY_ID = settings.AGENCY_ID
REDIS_HOST = settings.REDIS_HOST
REDIS_PORT = settings.REDIS_PORT


app.config = settings.API_KEY
app.config = settings.AGENCY_ID
app.config = settings.DATABASE_URL

app.include_router(bus_router)
app.include_router(route_api_router)

# Enable rich's enhanced traceback formatting
install(show_locals=True)

# Create a rich console instance
console = Console()

url = f"http://localhost:8000/nearby-stops?lat=37.7749&lon=-122.4194&radius=500"
url1 = f"http://127.0.0.1:8000/get-route-details?route_short_name=Green-N"

'''
    http://127.0.0.1:8000/get-all-routes
    http://127.0.0.1:8000/update-routes
    http://127.0.0.1:8000/get-route-details?route_id=5R
    http://127.0.0.1:8000/bus-positions?bus_number=5
    http://api.511.org/transit/StopMonitoring?api_key=d11301a5-2cb9-4c4a-ad47-b449ed6794c0&agency=SF&stop_id=14212&format=json"
    http://127.0.0.1:8000/get-route-details?bus_number=Green-N
    http://127.0.0.1:8000/get-route-details?route_short_name=Green-N
    http://127.0.0.1:8000/bus-positions?bus_number=5R&agency=SF
    http://api.511.org/transit/RouteDetails?api_key=d11301a5-2cb9-4c4a-ad47-b449ed6794c0&agency=SF&route_id=Orange-N&format=json
    curl "http://127.0.0.1:8000/get-route-details?route_short_name=Orange-N&route_id=5R"
    curl "http://127.0.0.1:8000/get-route-details?route_short_name=Green-N"
    curl "http://127.0.0.1:8000/bus-positions?bus_number=5R&agency=SF"
    http://127.0.0.1:8000/bus-positions?bus_number=14&agency=SF
    curl  "http://localhost:8000/plan-route?start_lat=37.7749&start_lon=-122.4194&end_lat=37.7833&end_lon=-122.4167"
    curl  "http://localhost:8000/nearby-stops?lat=37.7749&lon=-122.4194&radius=500"
    http://127.0.0.1:8000/arrival/calculate?destination=Mission%20St%20%26%20Main%20St&arrival_time=2025-03-02T18:07:48Z
    http://127.0.0.1:8000/arrival/estimate-arrival?bus_number=5&stop_name=Mission St & 24th St
    http://127.0.0.1:8000/arrival/calculate?destination=Mission St & Main St&arrival_time=2025-03-02T18:07:48Z
    url2 = f"http://127.0.0.1:8000/routes/plan-trip?user_lat=37.7737045&user_lon=-122.462646&dest_address=37.754528,-122.40934"
    curl -X GET http://127.0.0.1:8000/openapi.json | jq
    
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    sudo systemctl status postgresql
    sudo systemctl disable postgresql
    sudo -u postgres psql
    
    cd backend
    uvicorn app.main:app --reload

    cd frontend
    npm run dev
    
'''
def test_api_endpoints():
    console.rule("[bold blue]MuniBuddy API Testing Tool[/bold blue]")
    
    # Example request
    url = "http://localhost:8000/nearby-stops?lat=37.7749&lon=-122.4194&radius=500"
    
    try:
        console.print(Panel.fit(f"[bold cyan]GET[/bold cyan] {url}"))
        response = requests.get(url)
        
        # Format JSON response for better readability
        if response.status_code == 200:
            try:
                json_data = response.json()
                console.print("[bold green]Success![/bold green] Status code:", response.status_code)
                console.print(Panel(Syntax(json.dumps(json_data, indent=2), "json", theme="monokai")))
            except:
                console.print("[yellow]Raw response:[/yellow]")
                console.print(Panel(response.text[:500]))
        else:
            console.print("[bold red]Error![/bold red] Status code:", response.status_code)
            console.print(response.text)
            
    except requests.exceptions.RequestException as e:
        console.print("[bold red]Error while fetching API data:[/bold red]")
        console.print(Panel(str(e)))

if __name__ == "__main__":
    test_api_endpoints()