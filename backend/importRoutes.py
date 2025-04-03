import pandas as pd
from app.db.database import SessionLocal
from app.models.bus_route import BusRoute

def import_gtfs_routes():
    df = pd.read_csv("gtfs_data/muni_gtfs-current/routes.txt")

    db = SessionLocal()

    for _, row in df.iterrows():
        route = BusRoute(
            route_id=row["route_id"],
            line_ref=row["route_short_name"] if "route_short_name" in row else row["route_id"],
            agency_id=row["agency_id"] if "agency_id" in row else "SFMTA",
            route_name=row["route_long_name"],
            direction="",  # opsiyonel alan
            origin="Unknown",
            destination="Unknown"
        )
        db.add(route)

    db.commit()
    db.close()
    print("✅ GTFS routes successfully imported.")

if __name__ == "__main__":
    import_gtfs_routes()
