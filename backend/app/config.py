# import os
# from pydantic_settings import BaseSettings
# from dotenv import load_dotenv

# load_dotenv()

# class Settings(BaseSettings):
#     API_KEY: str = os.getenv("API_KEY")
#     AGENCY_IDS: list[str] = os.getenv("AGENCY_ID", "SF").split(",")
#     GTFS_FEED_URL: str = "http://api.511.org/transit/gtfsfeed?api_key={api_key}&agency={agency}"
#     DATABASE_URL: str = os.getenv("DATABASE_URL")
    
#     class Config:
#         case_sensitive = True

# settings = Settings()
# print(f"[DEBUG] Config loaded. Agencies: {settings.AGENCY_IDS}")

import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
AGENCY_ID = os.getenv("AGENCY_ID", "SF").split(',')
DATABASE_URL = os.getenv("DATABASE_URL")
GTFS_FEED_URL = "http://api.511.org/transit/gtfsfeed?api_key={api_key}&agency={agency}"

