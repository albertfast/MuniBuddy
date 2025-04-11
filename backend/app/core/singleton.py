# app/core/singleton.py
from app.services.bus_service import BusService
from app.services.schedule_service import get_static_schedule


# Global singleton instances
bus_service = BusService()
scheduler_service = get_static_schedule()

# Export the singleton
__all__ = ["bus_service"]