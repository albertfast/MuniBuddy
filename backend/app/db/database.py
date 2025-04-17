import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load environment variables
load_dotenv()

# -- Require DATABASE_URL from .env --
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in the .env file")

# -- Optional DEBUG flag --
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=DEBUG  # Enable SQL debug logging if DEBUG=true
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for declarative models
Base = declarative_base()

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility to initialize DB tables from models
def init_db():
    Base.metadata.create_all(bind=engine)

# Cleanup engine
def cleanup_db():
    engine.dispose()