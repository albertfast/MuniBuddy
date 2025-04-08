# app/core/singleton.py
from app.services.bus_service import BusService
from app.db.database import get_db

# Initialize the BusService with the db parameter
db = next(get_db())  # Get a database session
bus_service = BusService(db)

# Export the singleton
__all__ = ["bus_service"]