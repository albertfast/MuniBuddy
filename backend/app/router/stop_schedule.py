import os
import sys
# Ensure the project root is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, Depends, HTTPException, Path # Path import edildi
# from sqlalchemy.orm import Session # Kaldırıldı (eğer BusService db kullanmıyorsa)
# from app.db.database import get_db # Kaldırıldı
from app.services.bus_service import BusService
from typing import Dict, Any # Tip ipuçları için

router = APIRouter()

# --- BusService Instance (Yine aynı seçenekler geçerli) ---
# Option 1: Global instance
bus_service = BusService()

# Option 2: Dependency Injection
# async def get_bus_service():
#     yield BusService() # Veya paylaşılan bir örnek

@router.get(
    "/stop-schedule/{stop_id}",
    response_model=Dict[str, Any], # Daha spesifik bir model daha iyi olabilir (örn: Pydantic)
    summary="Get Real-time and Static Schedule for a Stop"
    )
async def get_stop_schedule_endpoint(
    stop_id: str = Path(..., description="The unique ID of the transit stop (e.g., '1234')"),
    # db: Session = Depends(get_db) # Kaldırıldı
    # bus_service: BusService = Depends(get_bus_service) # Option 2 için
):
    """
    Retrieves the upcoming schedule for a specific stop ID.

    - Checks cache first.
    - Attempts to fetch real-time arrival predictions from the 511 API.
    - If real-time data is unavailable or empty, falls back to the static GTFS schedule.
    - Returns combined inbound and outbound arrivals (limited).
    """
    if not stop_id:
        raise HTTPException(status_code=400, detail="Stop ID cannot be empty.")

    print(f"[API /stop-schedule] Request for stop_id: {stop_id}")
    try:
        # Fonksiyon artık her zaman bir dict döndürmeli (veya hata fırlatmalı)
        schedule = await bus_service.get_stop_schedule(stop_id)
        # Schedule None olmamalı, en kötü ihtimalle {'inbound': [], 'outbound': []} döner
        # if schedule is None:
        #     # Bu durum artık BusService içinde ele alınıyor, buraya gelmemeli
        #     raise HTTPException(status_code=404, detail=f"Schedule information not found for stop {stop_id}.")

        return schedule
    except HTTPException as http_exc:
         # FastAPI tarafından bilinen hataları tekrar fırlat
         raise http_exc
    except Exception as e:
        # Beklenmedik sunucu hatalarını logla ve genel bir hata döndür
        print(f"[ERROR /stop-schedule] Unexpected error for stop {stop_id}: {e}")
        # import traceback # Detaylı debug için
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An internal error occurred while fetching the schedule for stop {stop_id}.")