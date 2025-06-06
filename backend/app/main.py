from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.db.database import init_db
from app.routers.nearby_stops import router as nearby_stops_router
from app.routers.bus_router import router as bus_router
from app.routers.bart_router import router as bart_router
from app.routers.stop_schedule import router as stop_schedule_router
from app.routers import routes_router
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

app.include_router(nearby_stops_router, prefix="/api/v1")
app.include_router(bus_router, prefix="/api/v1")
app.include_router(bart_router, prefix="/api/v1")
app.include_router(stop_schedule_router, prefix="/api/v1")
app.include_router(routes_router.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Welcome to MuniBuddy API — now supporting Muni & BART!"}

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "services_initialized": True
    }

@app.on_event("startup")
async def startup_event():
    print("🔄 Starting MuniBuddy API...")
    init_db()
    print("✅ Database initialized")