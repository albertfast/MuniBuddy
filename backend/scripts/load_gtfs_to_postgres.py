import os
import sys
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect
from time import sleep
from datetime import datetime

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

# --- Import app config and db ---
from app.config import settings
from app.db.database import engine

# --- Progress Bar ---
def print_progress_bar(iteration, total, prefix='', suffix='', length=40):
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_len = int(length * iteration // total)
    bar = '█' * filled_len + '-' * (length - filled_len)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r')
    if iteration == total:
        print()  # New line after done

def import_gtfs_to_postgres():
    inspector = inspect(engine)
    failed_tables = []
    loaded_tables = []
    skipped_tables = []

    print(f"\n🚀 Starting GTFS import to PostgreSQL...")

    for agency, data_dict in settings._gtfs_data.items():
        print(f"\n📦 Importing GTFS data for agency: {agency.upper()}")
        total = len(data_dict)
        for i, (table_name, df) in enumerate(data_dict.items(), start=1):
            print_progress_bar(i, total, prefix='Progress', suffix=table_name)

            if df.empty:
                skipped_tables.append((table_name, "empty or missing file"))
                continue

            if inspector.has_table(table_name):
                print(f"  [SKIPPED] {table_name}: table already exists.")
                skipped_tables.append((table_name, "already exists"))
                continue

            try:
                df.to_sql(table_name, engine, if_exists="replace", index=False, method="multi")
                loaded_tables.append((table_name, len(df)))
            except SQLAlchemyError as e:
                failed_tables.append((table_name, str(e)))

    print("\n✅ Import completed.")
    print(f"  → Loaded: {len(loaded_tables)} table(s)")
    print(f"  → Skipped: {len(skipped_tables)} table(s)")
    print(f"  → Failed: {len(failed_tables)} table(s)")

    # --- Save log to txt ---
    with open("gtfs_import_results.txt", "w") as f:
        f.write("MuniBuddy GTFS Import Summary\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"✔ Source Directory: {settings.GTFS_PATHS['muni']}\n")
        f.write(f"✔ PostgreSQL Connected: {engine.url.database}\n")
        f.write(f"✔ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("✅ Loaded Tables:\n")
        for t, count in loaded_tables:
            f.write(f"  - {t}: {count} rows\n")

        f.write("\n⏭️ Skipped Tables:\n")
        for t, reason in skipped_tables:
            f.write(f"  - {t}: {reason}\n")

        f.write("\n❌ Failed Tables:\n")
        for t, reason in failed_tables:
            f.write(f"  - {t}: {reason}\n")

if __name__ == "__main__":
    import_gtfs_to_postgres()
