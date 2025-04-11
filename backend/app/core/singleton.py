# app/core/singleton.py
from app.services.bus_service import BusService
from app.services.schedule_service import SchedulerService


# Global singleton instances
bus_service = BusService()
scheduler_service = SchedulerService()

# Export the singleton
__all__ = ["bus_service"]