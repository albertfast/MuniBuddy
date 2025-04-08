# app/core/singleton.py
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app.services.bus_service import BusService
from app.config import settings

# Create a database engine and session factory
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a database session
db_session = SessionLocal()

# Initialize the BusService singleton
bus_service = BusService(db=db_session)