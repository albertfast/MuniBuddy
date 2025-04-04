import os
from dotenv import load_dotenv
from typing import List, Optional, Dict
import pandas as pd
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "MuniBuddy"
    API_V1_STR: str = "/api/v1"
    AGENCY_ID: List[str]

    # Database
    DATABASE_URL: str = Field(default="postgresql://myuser:mypassword@localhost:5432/munibuddy_db")
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Debug & Logging
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = "INFO"

    # Transit API
    API_KEY: Optional[str] = None
    TRANSIT_511_BASE_URL: str = "http://api.511.org/transit"
    DEFAULT_AGENCY: str = "SFMTA"

    # GTFS Paths
    GTFS_AGENCIES: List[str] = ["muni", "bart"]
    GTFS_PATHS: Dict[str, str] = {
        "muni": os.path.abspath(os.path.join(os.path.dirname(__file__), "gtfs_data/muni_gtfs-current")),
        "bart": os.path.abspath(os.path.join(os.path.dirname(__file__), "gtfs_data/bart_gtfs-current"))
    }

    # GTFS loaded data
    gtfs_data: Dict[str, tuple] = {}

    @model_validator(mode="before")
    @classmethod
    def set_sqlalchemy_uri(cls, data: Dict) -> Dict:
        if not data.get("SQLALCHEMY_DATABASE_URI") and data.get("DATABASE_URL"):
            data["SQLALCHEMY_DATABASE_URI"] = data["DATABASE_URL"]
        return data

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