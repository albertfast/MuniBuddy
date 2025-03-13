import json

def clean_api_response(api_response):
    """Cleans and formats the JSON response from the API."""
    try:
        data = json.loads(api_response)
        return data
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format"}
