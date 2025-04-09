import os
import sys

# Go to backend/ directory and set it as root
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
from typing import List, Optional, Dict
import pandas as pd
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator, PrivateAttr, field_validator

# 👇 Add root folder so `from app...` imports work
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

load_dotenv()

class Settings(BaseSettings):
    # General Config
    PROJECT_NAME: str = "MuniBuddy"
    API_V1_STR: str = "/api/v1"

    # Agencies from .env (ex: '["SFMTA", "SF", "BA"]' or 'SFMTA,SF,BA')
    AGENCY_ID: List[str] = ["SFMTA"]

    @field_validator("AGENCY_ID", mode="before")
    @classmethod
    def parse_agency_id(cls, v):
        """Parse agency list from JSON string or comma-separated values"""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)  # Expects '["SFMTA", "SF", "BA"]'
            except json.JSONDecodeError:
                return v.split(",")  # Fallback to CSV format
        return v

    # Database Config
    DATABASE_URL: str = Field(default="postgresql://myuser:mypassword@postgres_db:5432/munibuddy_db")
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def set_sqlalchemy_uri(cls, data: Dict) -> Dict:
        """Auto-generate SQLALCHEMY_DATABASE_URI from DATABASE_URL if missing"""
        if not data.get("SQLALCHEMY_DATABASE_URI") and data.get("DATABASE_URL"):
            data["SQLALCHEMY_DATABASE_URI"] = data["DATABASE_URL"]
        return data

    # Redis Config
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Debug & Logging
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = "INFO"

    # Transit API (511.org)
    API_KEY: Optional[str] = None
    TRANSIT_511_BASE_URL: str = "http://api.511.org/transit"
    DEFAULT_AGENCY: str = "SFMTA"

    # GTFS Paths per agency (e.g., muni, bart)
    GTFS_AGENCIES: List[str] = ["muni", "bart"]
    GTFS_PATHS: Dict[str, str] = {
        "muni": "/app/gtfs_data/muni_gtfs-current",
        "bart": "/app/gtfs_data/bart_gtfs-current"
    }

    # Internal cache for loaded GTFS DataFrames (private, not validated)
    _gtfs_data: Dict[str, tuple] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def load_gtfs(self) -> "Settings":
        """Automatically load GTFS data from disk during settings initialization"""
        from app.services.gtfs_service import load_gtfs_data
        for agency, path in self.GTFS_PATHS.items():
            try:
                os.makedirs(path, exist_ok=True)
                self._gtfs_data[agency] = load_gtfs_data(path)
                print(f"[DEBUG] {path}: {len(self._gtfs_data[agency][2])} stops, {len(self._gtfs_data[agency][3])} stop_times, {len(self._gtfs_data[agency][1])} trips")
            except Exception as e:
                print(f"Error loading GTFS data for {agency}: {str(e)}")
        print(f"[DEBUG] Loaded GTFS for agencies: {list(self._gtfs_data.keys())}")
        return self

    def get_gtfs_data(self, agency: str) -> Optional[tuple]:
        """Returns the GTFS data tuple for the given agency (e.g., 'muni' or 'bart')"""
        return self._gtfs_data.get(agency)

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"

# ✅ Global settings instance to use across your project
settings = Settings()
