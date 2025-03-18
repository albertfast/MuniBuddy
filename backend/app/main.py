from fastapi import FastAPI, APIRouter
from app.config import settings
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


app = FastAPI()
from app.route_api import router as route_api
router = APIRouter()
app.include_router(route_api)

@app.get("/")
def home():
    return {"message": "MuniBuddy API is running"}
