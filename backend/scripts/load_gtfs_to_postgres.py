import os
import sys
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError

# --- Setup path to access `app` module ---
# Change working directory to backend root
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

# --- Now import settings and engine ---
from app.config import settings
from app.db.database import engine

def import_gtfs_to_postgres():
    failed_tables = []
    loaded_tables = []

    print(f"\n🚀 Starting GTFS import to PostgreSQL...")
    
    for agency, data_dict in settings._gtfs_data.items():
        print(f"\n📦 Importing GTFS data for agency: {agency.upper()}")

        for table_name, df in data_dict.items():
            if df.empty:
                print(f"  [SKIPPED] {table_name}: file is empty or not found.")
                failed_tables.append((table_name, "empty or missing file"))
                continue

            try:
                df.to_sql(table_name, engine, if_exists="replace", index=False)
                print(f"  [✓] Loaded {table_name} ({len(df)} rows)")
                loaded_tables.append(table_name)
            except SQLAlchemyError as e:
                print(f"  [ERROR] Failed to write {table_name}: {str(e)}")
                failed_tables.append((table_name, str(e)))

    print("\n✅ Import completed.")
    print(f"  → Successfully loaded: {len(loaded_tables)} table(s)")
    print(f"  → Failed/Skipped: {len(failed_tables)} table(s)\n")

    if failed_tables:
        print("🔍 Failed or Skipped Tables:")
        for name, reason in failed_tables:
            print(f"  - {name}: {reason}")

if __name__ == "__main__":
    import_gtfs_to_postgres()
