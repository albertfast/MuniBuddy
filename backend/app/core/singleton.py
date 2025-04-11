from app.services.bus_service import BusService

# Global singleton instances
bus_service = BusService()

# Export the singleton
__all__ = ["bus_service"]
