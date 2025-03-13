from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.bus_route import BusRoute

router = APIRouter()

@router.get("/gtfs-routes")
def get_gtfs_routes(db: Session = Depends(get_db)):
    """Fetch static GTFS routes."""
    return db.query(BusRoute).all()

@router.get("/get-route-details")
def get_route_details(route_id: str):
    """Belirtilen rota ID'sine göre rota bilgilerini döndürür."""
    return {"route_id": route_id, "status": "OK"}