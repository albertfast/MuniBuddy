from fastapi import APIRouter
from app.api.routes import transit

api_router = APIRouter()
api_router.include_router(transit.router, prefix="/transit", tags=["transit"]) 