import os
import sys
import pandas as pd

# Add backend/ to sys.path to resolve 'app' imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import SessionLocal
from app.models.bus_route import BusRoute

# GTFS routes.txt dosyasını oku
df = pd.read_csv("gtfs_data/muni_gtfs-current/routes.txt")

# Veritabanı oturumu oluştur
db = SessionLocal()

for _, row in df.iterrows():
    route = BusRoute(
        route_id=row["route_id"],
        line_ref=row.get("route_short_name"),
        agency_id="SFMTA",
        route_name=row.get("route_long_name"),
        direction=None,
        origin=None,
        destination=None
    )
    db.add(route)

db.commit()
db.close()

print("[SUCCESS] GTFS routes loaded into bus_routes table.")
