import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List, Optional

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "MuniBuddy"
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@localhost:5432/munibuddy_db")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "myuser")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "mypassword")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "munibuddy_db")
    SQLALCHEMY_DATABASE_URI: Optional[str] = None
    
    # Redis Configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    
    # Application Settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Transit Settings
    MAX_WALKING_DISTANCE: float = float(os.getenv("MAX_WALKING_DISTANCE", "0.5"))  # miles
    MAX_TRANSFER_DISTANCE: float = float(os.getenv("MAX_TRANSFER_DISTANCE", "0.25"))  # miles
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # seconds

    # 511.org API Configuration
    API_KEY: str = os.getenv("API_KEY")  # Required from .env file
    TRANSIT_511_BASE_URL: str = os.getenv("TRANSIT_511_BASE_URL", "http://api.511.org/transit")
    DEFAULT_AGENCY: str = os.getenv("DEFAULT_AGENCY", "SFMTA")

    # GTFS API Configuration
    AGENCY_ID_RAW: str = os.getenv("AGENCY_ID", '["SFMTA"]')
    AGENCY_ID: List[str] = eval(AGENCY_ID_RAW)  # Parse JSON array string
    GTFS_FEED_URL: str = f"http://api.511.org/transit/gtfsfeed?api_key={API_KEY}&agency={{agency}}"

    def __init__(self, **data):
        super().__init__(**data)
        # Use DATABASE_URL directly if provided, otherwise construct from components
        self.SQLALCHEMY_DATABASE_URI = self.DATABASE_URL or (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# For debugging
print(f"[DEBUG] Config loaded. Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}, DB: {settings.SQLALCHEMY_DATABASE_URI}")
print(f"[DEBUG] Config loaded. Agencies: {settings.AGENCY_ID}")
