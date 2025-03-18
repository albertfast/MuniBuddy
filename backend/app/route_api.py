from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.route_finder2 import *

API_KEY = settings.API_KEY
REDIS_HOST = settings.REDIS_HOST
REDIS_PORT = settings.REDIS_PORT

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "FastAPI is working!"}

@app.get("/optimized-route")
def find_optimized_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float, db: Session = Depends(get_db)
):
    start_stop = find_nearest_stop(start_lat, start_lon, db)
    end_stop = find_nearest_stop(end_lat, end_lon, db)

    if not start_stop or not end_stop:
        return {"error": "No nearby stops found"}

    return {
        "start_stop": {
            "stop_id": start_stop[0],
            "stop_name": start_stop[1],
            "lat": start_stop[2],
            "lon": start_stop[3]
        },
        "end_stop": {
            "stop_id": end_stop[0],
            "stop_name": end_stop[1],
            "lat": end_stop[2],
            "lon": end_stop[3]
        }
    }
