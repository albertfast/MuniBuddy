from fastapi import APIRouter

router = APIRouter()

@router.get("/bus-router")
def list_routes():
    return {"message": "Bus route model endpoint test"}