import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.singleton import bus_service

router = APIRouter()

@router.get("/gtfs-routes")
def get_gtfs_routes(db: Session = Depends(get_db)):
    """Fetch static GTFS routes."""
    return db.query(bus_service).all()

@router.get("/routes/{route_id}")
def get_route(route_id: str, db: Session = Depends(get_db)):
    """Returns route information for the specified route ID from the database."""
    route = db.query(bus_service).filter(bus_service.route_id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


from app.config import settings

@router.get("/get-route-details")
def get_route_details(route_id: str):
    """Returns GTFS static route info for the given route ID."""
    gtfs_data = settings.get_gtfs_data("muni")  # veya bart, istenirse parametre yapılabilir
    if not gtfs_data:
        raise HTTPException(status_code=500, detail="GTFS data not loaded")

    routes_df, _, _, _, _ = gtfs_data
    route_row = routes_df[routes_df["route_id"] == route_id]

    if route_row.empty:
        raise HTTPException(status_code=404, detail="Route not found in GTFS")

    return route_row.iloc[0].to_dict()
