import os
import sys

# Setup backend path
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

from sqlalchemy import create_engine, inspect, text
from app.config import settings
from datetime import datetime

# Initialize
engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
inspector = inspect(engine)
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

log_lines = []

def log(msg):
    print(msg)
    log_lines.append(msg)

# Start logging
log(f"\n🔌 Connected to DB: {engine.url.database}")
log(f"🕒 Timestamp: {timestamp}")
log("📋 Available tables:")

tables = inspector.get_table_names()
if not tables:
    log("  ⚠️ No tables found in the database.")
else:
    for table in tables:
        log(f"\n - {table}")

        # Primary key
        pk = inspector.get_pk_constraint(table).get("constrained_columns", [])
        log(f"   🔑 Primary Keys: {pk if pk else 'None'}")

        # Sample rows
        with engine.connect() as conn:
            try:
                result = conn.execute(text(f"SELECT * FROM {table} LIMIT 3")).fetchall()
                if result:
                    log("   📊 Sample Rows:")
                    for row in result:
                        log(f"     {dict(row)}")
                else:
                    log("   📭 No rows found.")
            except Exception as e:
                log(f"   ❌ Error reading rows: {e}")

# Save to file
with open("sqlalchemy_inspect_log.txt", "w") as f:
    f.write("\n".join(log_lines))

log("\n✅ Log saved to sqlalchemy_inspect_log.txt")
