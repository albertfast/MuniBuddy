from fastapi import APIRouter

router = APIRouter()

@router.get("/bus-routes")
def list_routes():
    return {"message": "Bus route model endpoint test"}