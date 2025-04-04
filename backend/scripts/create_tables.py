# backend/scripts/create_tables.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import Base, engine
from app.models import bus_route  # 👉 tüm modelleri import et

print("[INFO] Creating all tables...")
Base.metadata.create_all(bind=engine)
print("[SUCCESS] Tables created.")
