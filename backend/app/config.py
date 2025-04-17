import os
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional, Dict
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator, field_validator

# --- Load .env from project root ---
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

class Settings(BaseSettings):
    PROJECT_NAME: str = "MuniBuddy"
    API_V1_STR: str = "/api/v1"

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

    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def set_sqlalchemy_uri(cls, data: Dict) -> Dict:
        if not data.get("SQLALCHEMY_DATABASE_URI") and data.get("DATABASE_URL"):
            data["SQLALCHEMY_DATABASE_URI"] = data["DATABASE_URL"]
        return data

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    API_KEY: Optional[str] = None
    TRANSIT_511_BASE_URL: str = "http://api.511.org/transit"
    DEFAULT_AGENCY: str = "SF"

    GTFS_AGENCIES: List[str] = ["muni", "bart"]
    GTFS_PATHS: Dict[str, str] = {
        "muni": "/app/gtfs_data/muni_gtfs-current",
        "bart": "/app/gtfs_data/bart_gtfs-current"
    }

    def normalize_agency(self, agency: str, to_511: bool = False) -> str:
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

settings = Settings()
