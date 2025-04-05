from datetime import datetime
from fastapi import APIRouter, HTTPException
from app.config import settings

router = APIRouter()

@router.get("/stop-schedule/{stop_id}")
def get_stop_schedule(stop_id: str):
    """
    Returns the upcoming scheduled arrivals at the given stop.
    Only future departures from the current time are included.
    """
    try:
        # Load GTFS data
        _, _, stops_df, stop_times_df, trips_df, calendar_df = settings.get_gtfs_data("muni")

        # Get current time and day
        current_time = datetime.now().strftime("%H:%M:%S")
        current_day = datetime.now().strftime("%A").lower()  # e.g., 'monday'

        # Filter active services for today
        active_services = calendar_df[calendar_df[current_day] == "1"]["service_id"].tolist()

        # Get upcoming times for the given stop
        upcoming_times = stop_times_df[
            (stop_times_df["stop_id"] == stop_id) &
            (stop_times_df["departure_time"] > current_time)
        ]

        # Merge with trip info
        upcoming_with_trip = upcoming_times.merge(trips_df, on="trip_id")
        upcoming_with_trip = upcoming_with_trip[upcoming_with_trip["service_id"].isin(active_services)]

        # Sort and limit to next 4
        upcoming_with_trip = upcoming_with_trip.sort_values("departure_time").head(4)

        # Format response
        results = []
        for _, row in upcoming_with_trip.iterrows():
            results.append({
                "route_id": row["route_id"],
                "trip_headsign": row["trip_headsign"],
                "arrival_time": row["arrival_time"],
                "departure_time": row["departure_time"],
                "direction": row["direction_id"]
            })

        if not results:
            return {"message": "No upcoming buses at this stop."}

        return {"stop_id": stop_id, "upcoming_arrivals": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
