# scripts/import_routes.py

import pandas as pd
from app.db.database import SessionLocal
from app.models.bus_route import BusRoute

# GTFS dosya yolu
routes_path = "/home/asahiner/Projects/MuniBuddy/backend/gtfs_data/muni_gtfs-current/routes.txt"

def import_gtfs_routes():
    df = pd.read_csv(routes_path)

    db = SessionLocal()
    for _, row in df.iterrows():
        route = BusRoute(
            route_id=row["route_id"],
            line_ref=row["route_short_name"],
            agency_id=row["agency_id"] if "agency_id" in row else "SFMTA",
            route_name=row["route_long_name"],
            direction="",     
            origin="Unknown",   
            destination="Unknown"
        )
        db.add(route)

    db.commit()
    db.close()
    print("✅ GTFS route verileri başarıyla yüklendi.")

if __name__ == "__main__":
    import_gtfs_routes()
