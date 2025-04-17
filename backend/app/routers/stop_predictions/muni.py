from app.services.realtime_service import fetch_real_time_stop_data
from app.services.schedule_service import SchedulerService

async def get_muni_predictions(stop_id: str):
    realtime = await fetch_real_time_stop_data(stop_id, agency="muni")
    if not realtime.get("inbound") and not realtime.get("outbound"):
        return SchedulerService().get_schedule(stop_id, agency="muni")

    for entry in realtime.get("inbound", []) + realtime.get("outbound", []):
        entry.setdefault("vehicle", {"lat": "", "lon": ""})

    return realtime
