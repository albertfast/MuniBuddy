from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.singleton import bus_service  # ✅ Singleton BusService instance
from app.db.database import init_db

# Routers
from app.routers.nearby_stops import router as nearby_stops_router
from app.routers.nearby_bus_positions import router as nearby_bus_router
from app.routers.stop_schedule import router as stop_schedule_router
from app.routers.deploy import router as deploy_router

app = FastAPI(
    title="MuniBuddy API",
    description="Transit info and route planner for SF",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific domain(s) in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Mount API routers with versioning
app.include_router(nearby_stops_router, prefix="/api/v1", tags=["Nearby Stops"])
app.include_router(nearby_bus_router, prefix="/api/v1", tags=["Nearby Bus Positions"])
app.include_router(stop_schedule_router, prefix="/api/v1", tags=["Stop Schedule"])
app.include_router(deploy_router, prefix="/api/v1/deploy", tags=["Deploy"])

# Root route
@app.get("/")
async def root():
    return {"message": "Welcome to MuniBuddy!"}

# Health check
@app.get("/health")
def health_check():
    return {"status": "ok"}

# Optional: Initialize DB on script run
if __name__ == "__main__":
    init_db()
