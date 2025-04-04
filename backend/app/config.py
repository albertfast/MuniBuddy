import os
from dotenv import load_dotenv
from typing import List, Optional
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "MuniBuddy"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@localhost:5432/munibuddy_db")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "myuser")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "mypassword")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "munibuddy_db")
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")

    # App Settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Transit
    MAX_WALKING_DISTANCE: float = float(os.getenv("MAX_WALKING_DISTANCE", "0.5"))
    MAX_TRANSFER_DISTANCE: float = float(os.getenv("MAX_TRANSFER_DISTANCE", "0.25"))
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))

    # 511.org API
    API_KEY: str = os.getenv("API_KEY")
    TRANSIT_511_BASE_URL: str = os.getenv("TRANSIT_511_BASE_URL", "http://api.511.org/transit")
    DEFAULT_AGENCY: str = os.getenv("DEFAULT_AGENCY", "SFMTA")

    # GTFS Config
    AGENCY_ID_RAW: str = os.getenv("AGENCY_ID", '["SFMTA"]')
    AGENCY_ID: List[str] = eval(AGENCY_ID_RAW)
    MUNI_GTFS_PATH: str = os.getenv(
        "MUNI_GTFS_PATH",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "gtfs_data/muni_gtfs-current"))
    )

    def __init__(self, **data):
        super().__init__(**data)

        self.SQLALCHEMY_DATABASE_URI = self.DATABASE_URL or (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
        )

        os.makedirs(self.MUNI_GTFS_PATH, exist_ok=True)

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

print(f"[DEBUG] Config loaded. Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}, DB: {settings.SQLALCHEMY_DATABASE_URI}")
print(f"[DEBUG] Config loaded. Agencies: {settings.AGENCY_ID}")
print(f"[DEBUG] GTFS Path: {settings.MUNI_GTFS_PATH}")
