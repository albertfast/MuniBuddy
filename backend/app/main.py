from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.core.singleton import bus_service, schedule_service, bart_service
from app.db.database import init_db

from app.routers.stop_predictions_router import (
    stop_predictions_router,
    bus_router,
    bart_router,
    stop_schedule_router,
    bus_positions_router,
)

load_dotenv()

app = FastAPI(
    title="MuniBuddy API",
    description="Transit info and route planner for SF (Muni + BART)",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bus_router, prefix="/api/v1")
app.include_router(bart_router, prefix="/api/v1")
app.include_router(stop_predictions_router, prefix="/api/v1")
app.include_router(stop_schedule_router, prefix="/api/v1")
app.include_router(bus_positions_router, prefix="/api/v1")

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
    _ = bus_service
    _ = schedule_service
    _ = bart_service
    print("✅ Services initialized: Bus, Scheduler, BART")