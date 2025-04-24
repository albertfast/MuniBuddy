from fastapi import APIRouter, Query, HTTPException
from app.config import settings
from app.services.stop_helper import load_stops
import httpx

router = APIRouter(prefix="/bart-positions", tags=["BART Positions"])

@router.get("/by-stop")
async def get_bart_predictions_by_stop(
    stopCode: str = Query(...),
    agency: str = Query(default="bart")
):
    norm_agency = settings.normalize_agency(agency, to_511=True)

    bart_stops = load_stops("bart")
    valid_stop_codes = {s.get("stop_code") for s in bart_stops if s.get("stop_code")}
    
    if stopCode not in valid_stop_codes:
        raise HTTPException(status_code=404, detail=f"{stopCode} is not a valid BART stop")

    url = "https://api.bart.gov/api/etd.aspx"
    params = {
        "cmd": "etd",
        "orig": stopCode,
        "key": settings.BART_API_KEY,
        "json": "y"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            raw_data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch BART data: {e}")

    station_data = raw_data.get("root", {}).get("station", [])
    if not station_data:
        return {"inbound": [], "outbound": []}

    station = station_data[0]
    results = {"inbound": [], "outbound": []}

    for etd in station.get("etd", []):
        destination = etd.get("destination")
        for estimate in etd.get("estimate", []):
            minutes = estimate.get("minutes")
            minutes_int = 0 if minutes == "Leaving" else int(minutes)
            direction = estimate.get("direction", "").lower()
            route_color = estimate.get("color")
            vehicle_length = estimate.get("length")

            formatted = {
                "route_number": etd.get("abbreviation"),
                "destination": destination,
                "arrival_time": f"{minutes} min",
                "minutes_until": minutes_int,
                "platform": estimate.get("platform"),
                "direction": direction,
                "color": route_color,
                "length": vehicle_length,
                "hexcolor": estimate.get("hexcolor")
            }

            if direction == "south":
                results["outbound"].append(formatted)
            else:
                results["inbound"].append(formatted)

    return results
