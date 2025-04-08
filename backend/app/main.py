from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.singleton import bus_service
from app.router.nearby_stops import router as nearby_stops_router
from app.router.stop_predictions import router as stop_predictions_router
from app.router.nearby_bus_positions import router as nearby_bus_router
from app.router.stop_schedule import router as stop_schedule_router
from app.router.deploy import router as deploy_router
from app.db.database import init_db

app = FastAPI(
    title="MuniBuddy API",
    description="Transit info and route planner for SF",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include routers
app.include_router(nearby_stops_router, prefix="/api/v1", tags=["Nearby Stops"])
app.include_router(stop_predictions_router, prefix="/api/v1", tags=["Stop Predictions"])
app.include_router(nearby_bus_router, prefix="/api/v1", tags=["Nearby Bus Positions"])
app.include_router(stop_schedule_router, prefix="/api/v1", tags=["Stop Schedule"])
app.include_router(deploy_router, prefix="/api/v1/deploy", tags=["Deploy"])

@app.get("/")
async def root():
    return {"message": "Welcome to MuniBuddy!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    init_db()
