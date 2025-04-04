import os
from dotenv import load_dotenv
from typing import List, Optional, Dict
import pandas as pd
from pydantic_settings import BaseSettings
from pydantic import Field

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "MuniBuddy"
    API_V1_STR: str = "/api/v1"
    AGENCY_ID: List[str] = Field(default_factory=lambda: os.getenv("AGENCY_ID", "SFMTA").split(","))

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@localhost:5432/munibuddy_db")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")

    # Debug & Logging
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Transit API
    API_KEY: str = os.getenv("API_KEY")
    TRANSIT_511_BASE_URL: str = os.getenv("TRANSIT_511_BASE_URL", "http://api.511.org/transit")
    DEFAULT_AGENCY: str = os.getenv("DEFAULT_AGENCY", "SFMTA")

    # GTFS Paths for multiple agencies
    GTFS_AGENCIES: List[str] = ["muni", "bart"]
    GTFS_PATHS: Dict[str, str] = {
        "muni": os.path.abspath(os.path.join(os.path.dirname(__file__), "gtfs_data/muni_gtfs-current")),
        "bart": os.path.abspath(os.path.join(os.path.dirname(__file__), "gtfs_data/bart_gtfs-current"))
    }

    # Will store loaded GTFS DataFrames
    gtfs_data: Dict[str, tuple] = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        from app.services.gtfs_service import load_gtfs_data

        for agency, path in self.GTFS_PATHS.items():
            os.makedirs(path, exist_ok=True)
            self.gtfs_data[agency] = load_gtfs_data(path)

        print(f"[DEBUG] Loaded GTFS for agencies: {list(self.gtfs_data.keys())}")

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()