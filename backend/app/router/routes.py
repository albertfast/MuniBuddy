from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.bus_route import BusRoute

router = APIRouter()

@router.get("/gtfs-routes")
def get_gtfs_routes(db: Session = Depends(get_db)):
    """Fetch static GTFS routes."""
    return db.query(BusRoute).all()

@router.get("/routes/{route_id}")
def get_route(route_id: str, db: Session = Depends(get_db)):
    """Returns route information for the specified route ID."""

@router.get("/get-route-details")
def get_route_details(route_id: str):
    """Returns route information for the specified route ID."""