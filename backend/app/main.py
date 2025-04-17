from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Core singleton services
from app.core.singleton import bus_service, scheduler_service, bart_service
from app.db.database import init_db

# Routers
from app.routers.nearby_stops import router as nearby_stops_router
from app.routers.bart_routes import router as bart_router
from app.routers.stop_predictions import router as stop_predictions_router
from app.routers.bart_monitor_stop import router as bart_monitor_router
from app.routers.nearby_bus_positions import router as nearby_bus_router
from app.routers.stop_schedule import router as stop_schedule_router

load_dotenv()

app = FastAPI(
    title="MuniBuddy API",
    description="Transit info and route planner for SF (Muni + BART)",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ✅ Consider narrowing in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router Registration
app.include_router(nearby_stops_router, prefix="/api/v1", tags=["Nearby Stops"])
app.include_router(stop_predictions_router, prefix="/api/v1", tags=["Stop Predictions"])
app.include_router(nearby_bus_router, prefix="/api/v1", tags=["Nearby Bus Positions"])
app.include_router(bart_router, prefix="/api/v1", tags=["BART"])
app.include_router(bart_monitor_router, prefix="/api/v1", tags=["BART Monitor"])
app.include_router(stop_schedule_router, prefix="/api/v1", tags=["Stop Schedule"])

@app.get("/")
async def root():
    return {"message": "Welcome to MuniBuddy API — now supporting Muni & BART!"}

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "bus_service": True,
        "scheduler_service": True,
        "bart_service": True
    }

@app.on_event("startup")
async def startup_event():
    print("🔄 Starting MuniBuddy API...")
    init_db()

    # Ensure singletons are triggered
    _ = bus_service
    _ = scheduler_service
    _ = bart_service
    print("✅ Services initialized: Bus, Scheduler, BART")
