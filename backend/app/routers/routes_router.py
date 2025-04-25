# backend/app/routers/routes_router.py
from fastapi import APIRouter
from app.services.stations_data import routes

router = APIRouter()

@router.get("/routes/{line}")
def get_route_stations(line: str):
    route = routes.get(line.upper())
    if route:
        return {
            "iconUp": route["iconUp"],
            "iconDown": route["iconDown"],
            "stations": route["stations"]
        }
    return {"error": "Route not found"}
