import os
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional, Dict
from pydantic_settings import BaseSettings
from app.services.gtfs_service import load_gtfs_data
from pydantic import Field, model_validator, PrivateAttr, field_validator
import pandas as pd

# --- Load .env from project root ---
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# --- Settings class ---
class Settings(BaseSettings):
    # General
    PROJECT_NAME: str = "MuniBuddy"
    API_V1_STR: str = "/api/v1"

    # Agencies (e.g. ["muni", "bart"])
    AGENCY_ID: List[str] = ["muni", "bart"]

    @field_validator("AGENCY_ID", mode="before")
    @classmethod
    def parse_agency_id(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v.split(",")
        return v

    # Database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def set_sqlalchemy_uri(cls, data: Dict) -> Dict:
        if not data.get("SQLALCHEMY_DATABASE_URI") and data.get("DATABASE_URL"):
            data["SQLALCHEMY_DATABASE_URI"] = data["DATABASE_URL"]
        return data

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Logging
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # 511 Transit API
    API_KEY: Optional[str] = None
    TRANSIT_511_BASE_URL: str = "http://api.511.org/transit"
    DEFAULT_AGENCY: str = "SF"  # 511 format

    # GTFS static files
    GTFS_AGENCIES: List[str] = ["muni", "bart"]
    GTFS_PATHS: Dict[str, str] = {
        "muni": "/app/gtfs_data/muni_gtfs-current",
        "bart": "/app/gtfs_data/bart_gtfs-current"
    }

    # GTFS cache
    self.gtfs_data[agency] = load_gtfs_data(path)
    gtfs_data: Dict[str, tuple] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def load_gtfs(self) -> "Settings":
        from app.services.gtfs_service import load_gtfs_data
        for agency, path in self.GTFS_PATHS.items():
            try:
                os.makedirs(path, exist_ok=True)
                self.gtfs_data[agency] = load_gtfs_data(path)
                print(f"[DEBUG] {path}: {len(self.gtfs_data[agency][2])} stops, "
                      f"{len(self.gtfs_data[agency][3])} stop_times, "
                      f"{len(self.gtfs_data[agency][1])} trips")
            except Exception as e:
                print(f"[GTFS ERROR] {agency}: {str(e)}")
        return self

    def get_gtfs_data(self, agency: str) -> Optional[tuple]:
        return self.gtfs_data.get(agency)

    def normalize_agency(self, agency: str, to_511: bool = False) -> str:
        """
        Normalize agency names across GTFS and 511 API usage.
        to_511=True → returns 511-compatible agency code (e.g. SF, BA)
        to_511=False → returns internal GTFS code (e.g. muni, bart)
        """
        agency = agency.strip().lower()
        muni_aliases = {"sf", "sfmta", "muni"}
        bart_aliases = {"ba", "bart"}

        if agency in muni_aliases:
            return "SF" if to_511 else "muni"
        elif agency in bart_aliases:
            return "BA" if to_511 else "bart"

        return agency.upper() if to_511 else agency.lower()

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"

# Instantiate settings
settings = Settings()
