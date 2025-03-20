import json
from typing import Any, Dict, Optional
from datetime import datetime

def clean_api_response(api_response: str) -> Dict[str, Any]:
    """
    Cleans and validates the JSON response from the API.
    
    Args:
        api_response (str): Raw JSON string from the API
        
    Returns:
        dict: Cleaned and validated JSON data
    """
    try:
        data = json.loads(api_response)
        
        # Remove empty or null values
        if isinstance(data, dict):
            data = {k: v for k, v in data.items() if v is not None}
            
        # Format dates if present
        if isinstance(data, dict) and "ExpectedArrivalTime" in data:
            try:
                data["ExpectedArrivalTime"] = datetime.fromisoformat(
                    data["ExpectedArrivalTime"].replace("Z", "+00:00")
                ).isoformat()
            except (ValueError, TypeError):
                pass
                
        # Ensure numeric values are properly typed
        if isinstance(data, dict):
            for key in ["Latitude", "Longitude"]:
                if key in data and data[key] is not None:
                    try:
                        data[key] = float(data[key])
                    except (ValueError, TypeError):
                        pass
                        
        return data

    except json.JSONDecodeError as e:
        return {
            "error": "Invalid JSON format",
            "details": str(e)
        }