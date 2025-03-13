import requests
import zipfile
import io
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve API Key and Operator ID from environment variables
API_KEY = os.getenv("API_KEY")
OPERATOR_ID = os.getenv("AGENCY_ID")  # Agency ID from .env

# Define the API URL for GTFS data download
url = f"http://api.511.org/transit/datafeeds?api_key={API_KEY}&operator_id={OPERATOR_ID}"

# Send request to the API
response = requests.get(url)
if response.status_code == 200:
    # Define the target directory
    target_dir = "gtfs_data"

    # Create the directory if it does not exist
    os.makedirs(target_dir, exist_ok=True)

    # Extract ZIP file contents into the target directory
    with zipfile.ZipFile(io.BytesIO(response.content), "r") as zip_ref:
        zip_ref.extractall(target_dir)

    print(f"GTFS data successfully downloaded and extracted to {target_dir}")
else:
    print("Error:", response.status_code)