import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List

# .env dosyasını yükle
load_dotenv()

class Settings(BaseSettings):
    API_KEY: str = os.getenv("API_KEY", "")

    # Redis Config
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))

    # PostgreSQL Config
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # GTFS API
    AGENCY_ID_RAW: str = os.getenv("AGENCY_ID", "SF")  
    AGENCY_ID: List[str] = AGENCY_ID_RAW.split(',')

    GTFS_FEED_URL: str = f"http://api.511.org/transit/gtfsfeed?api_key={API_KEY}&agency={{agency}}"

    class Config:
        case_sensitive = True

settings = Settings()

# Debugging için çıktılar
print(f"[DEBUG] Config loaded. Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}, DB: {settings.DATABASE_URL}")
print(f"[DEBUG] Config loaded. Agencies: {settings.AGENCY_ID}")
