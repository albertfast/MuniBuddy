from app.routers.bus_routes import router as bus_router
from app.routers.bart_routes import router as bart_router
from app.routers.stop_predictions.base import router as stop_predictions_router
from app.routers.nearby_stops import router as nearby_stops_router
from app.routers.stop_schedule import router as stop_schedule_router

__all__ = [
    "bus_router",
    "bart_router",
    "stop_predictions_router",
    "nearby_stops_router",
    "stop_schedule_router",
]
