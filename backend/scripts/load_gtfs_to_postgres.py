import os
import sys
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect
from datetime import datetime

# Setup project path
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

# Imports
from app.config import settings
from app.db.database import engine

# Progress bar
def print_progress_bar(iteration, total, prefix='', suffix='', length=40):
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_len = int(length * iteration // total)
    bar = '█' * filled_len + '-' * (length - filled_len)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r')
    if iteration == total:
        print()

# Main import logic
def import_gtfs_to_postgres():
    inspector = inspect(engine)
    full_log = []
    total_loaded = []
    total_skipped = []
    total_failed = []

    print(f"\n🚀 Starting GTFS import to PostgreSQL...\n")

    # Prioritize BART over MUNI
    for agency in ["bart", "muni"]:
        if agency not in settings._gtfs_data:
            print(f"⚠️ No GTFS data found for: {agency}")
            continue

        data_dict = settings.gtfs_data[agency]
        loaded_tables = []
        skipped_tables = []
        failed_tables = []

        print(f"\n📦 Importing {agency.upper()} data")
        total = len(data_dict)

        for i, (table_name, df) in enumerate(data_dict.items(), start=1):
            full_table = f"{agency}_{table_name}"
            print_progress_bar(i, total, prefix="Progress", suffix=full_table)

            if df.empty:
                skipped_tables.append((full_table, "empty or missing file"))
                continue

            if inspector.has_table(full_table):
                skipped_tables.append((full_table, "already exists"))
                continue

            try:
                use_chunksize = len(df) > 50000
                df.to_sql(full_table, engine, if_exists="replace", index=False,
                          method="multi", chunksize=5000 if use_chunksize else None)
                loaded_tables.append((full_table, len(df)))
            except SQLAlchemyError as e:
                failed_tables.append((full_table, str(e)))

        total_loaded.extend(loaded_tables)
        total_skipped.extend(skipped_tables)
        total_failed.extend(failed_tables)

        # Print section summary
        print(f"\n✅ {agency.upper()} Loaded: {len(loaded_tables)}")
        print(f"⏭️  {agency.upper()} Skipped: {len(skipped_tables)}")
        print(f"❌ {agency.upper()} Failed: {len(failed_tables)}")

        full_log.append({
            "agency": agency,
            "loaded": loaded_tables,
            "skipped": skipped_tables,
            "failed": failed_tables
        })

    engine.dispose()

    # Write to file
    with open("gtfs_import_results.txt", "w") as f:
        f.write("MuniBuddy GTFS Import Summary\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"✔ PostgreSQL Connected: {engine.url.database}\n")
        f.write(f"✔ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for log in full_log:
            f.write(f"--- {log['agency'].upper()} ---\n")
            f.write(f"✅ Loaded Tables:\n")
            for t, count in log['loaded']:
                f.write(f"  - {t}: {count} rows\n")
            f.write(f"\n⏭️ Skipped Tables:\n")
            for t, reason in log['skipped']:
                f.write(f"  - {t}: {reason}\n")
            f.write(f"\n❌ Failed Tables:\n")
            for t, reason in log['failed']:
                f.write(f"  - {t}: {reason}\n")
            f.write("\n")

        f.write("🏁 Final Summary\n")
        f.write(f"Total Loaded: {len(total_loaded)}\n")
        f.write(f"Total Skipped: {len(total_skipped)}\n")
        f.write(f"Total Failed: {len(total_failed)}\n")

if __name__ == "__main__":
    import_gtfs_to_postgres()
