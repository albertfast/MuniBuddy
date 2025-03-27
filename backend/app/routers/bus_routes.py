from typing import Dict, Any
from fastapi import APIRouter, Query, Depends
from services.bus_service import BusService

router = APIRouter()

def get_bus_service() -> BusService:
    return BusService()

@router.get("/nearby-by-address/{address}")
async def get_nearby_by_address(
    address: str,
    radius: float = Query(default=0.1, description="Search radius in miles"),
    bus_service: BusService = Depends(get_bus_service)
) -> Dict[str, Any]:
    """
    Get nearby bus stops and their schedules based on an address.
    
    Args:
        address (str): Address to search near
        radius (float): Search radius in miles
        
    Returns:
        Dict[str, Any]: Dictionary with nearby stops and their schedules
    """
    return await bus_service.find_stops_by_address(address, radius) 