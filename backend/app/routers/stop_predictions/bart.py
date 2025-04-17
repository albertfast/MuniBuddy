from app.core.singleton import bart_service, schedule_service

async def get_bart_predictions(stop_id: str, lat: float = None, lon: float = None):
    detailed = await bart_service.get_bart_stop_details(stop_id)
    realtime = await bart_service.get_real_time_arrivals(stop_id, lat, lon)

    if not realtime.get("inbound") and not realtime.get("outbound"):
        detailed["realtime"] = schedule_service.get_schedule(stop_id, agency="bart")
    else:
        for entry in realtime.get("inbound", []) + realtime.get("outbound", []):
            entry.setdefault("vehicle", {"lat": "", "lon": ""})
        detailed["realtime"] = realtime

    return detailed
