from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from redis import Redis
import requests
import json
from app.database import get_db
from app.config import settings
from app.route_finder2 import a_star_search, find_nearest_stop
from app.utils.xml_parser import xml_to_json
from app.services.bus_service import fetch_real_time_bus_data

app = FastAPI()

# Redis Bağlantısı
redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)

@app.get("/api/get_bus_route")
def get_bus_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, db: Session = Depends(get_db)):
    """ En iyi otobüs rotasını bulur ve gerçek zamanlı verileri ekler """

    cache_key = f"route:{start_lat},{start_lon}-{end_lat},{end_lon}"
    cached_route = redis.get(cache_key)
    if cached_route:
        return json.loads(cached_route)  # Önbellekten getir

    start_stop = find_nearest_stop(start_lat, start_lon, db)
    end_stop = find_nearest_stop(end_lat, end_lon, db)
    if not start_stop or not end_stop:
        raise HTTPException(status_code=404, detail="No nearby stops found.")

    # 511 API’den canlı otobüs verilerini çek
    live_buses = fetch_real_time_bus_data()

    # A* ile en iyi otobüs rotasını hesapla
    best_route = a_star_search(start_stop, end_stop, live_buses, db)
    if not best_route:
        raise HTTPException(status_code=404, detail="No optimal route found.")

    redis.setex(cache_key, 300, json.dumps(best_route))  # 5 dakika cache
    return best_route

@app.get("/api/get_real_time_buses")
def get_real_time_buses():
    """ 511 API'den gerçek zamanlı otobüs verilerini getirir """
    return fetch_real_time_bus_data()

@app.get("/api/convert_xml")
def convert_xml_to_json(xml_data: str):
    """ XML formatındaki veriyi JSON’a dönüştürür """
    return xml_to_json(xml_data)

@app.get("/api/get_gtfs_routes")
def get_gtfs_routes(db: Session = Depends(get_db)):
    """ PostgreSQL’de kayıtlı olan GTFS rotalarını getirir """
    query = "SELECT * FROM bus_routes;"
    routes = db.execute(query).fetchall()
    return [{"route_id": r[1], "name": r[3]} for r in routes]
