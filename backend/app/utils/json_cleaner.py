import json
from typing import Any, Dict, Optional
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama for colored output
init()

def clean_api_response(api_response: str) -> Dict[str, Any]:
    """
    Cleans and validates the JSON response from the API.
    
    Args:
        api_response (str): Raw JSON string from the API
        
    Returns:
        dict: Cleaned and validated JSON data
    """
    try:
        # Remove BOM if present
        if api_response.startswith('\ufeff'):
            api_response = api_response[1:]
            print(f"{Fore.CYAN}ℹ️ Removed BOM character from response{Style.RESET_ALL}")
            
        # Try to parse JSON
        try:
            data = json.loads(api_response)
            print(f"{Fore.GREEN}✓ Successfully parsed JSON response{Style.RESET_ALL}")
        except json.JSONDecodeError as e:
            print(f"{Fore.RED}✗ Failed to parse JSON: {str(e)}{Style.RESET_ALL}")
            return {
                "error": "Invalid JSON format",
                "details": str(e)
            }
        
        # Remove empty or null values
        if isinstance(data, dict):
            data = {k: v for k, v in data.items() if v is not None}
            print(f"{Fore.CYAN}ℹ️ Removed null values from response{Style.RESET_ALL}")
            
        # Check for required fields
        if isinstance(data, dict):
            service_delivery = data.get("ServiceDelivery")
            if not service_delivery:
                print(f"{Fore.RED}✗ Missing ServiceDelivery in response{Style.RESET_ALL}")
                return {
                    "error": "Missing required field",
                    "details": "ServiceDelivery not found in response"
                }
                
            stop_monitoring = service_delivery.get("StopMonitoringDelivery")
            if not stop_monitoring:
                print(f"{Fore.RED}✗ Missing StopMonitoringDelivery in response{Style.RESET_ALL}")
                return {
                    "error": "Missing required field",
                    "details": "StopMonitoringDelivery not found in response"
                }
                
            # StopMonitoringDelivery bir liste değilse, tek öğeyi listeye çevir
            if not isinstance(stop_monitoring, list):
                print(f"{Fore.YELLOW}⚠️ Converting StopMonitoringDelivery to list{Style.RESET_ALL}")
                service_delivery["StopMonitoringDelivery"] = [stop_monitoring]
                
            print(f"{Fore.GREEN}✓ Required fields are present{Style.RESET_ALL}")
            
        # Format dates if present
        if isinstance(data, dict):
            def format_date(value):
                if isinstance(value, str) and value.endswith('Z'):
                    try:
                        return datetime.fromisoformat(
                            value.replace("Z", "+00:00")
                        ).isoformat()
                    except (ValueError, TypeError):
                        return value
                elif isinstance(value, dict):
                    return {k: format_date(v) for k, v in value.items()}
                elif isinstance(value, list):
                    return [format_date(item) for item in value]
                return value
            
            data = format_date(data)
            print(f"{Fore.CYAN}ℹ️ Formatted dates in response{Style.RESET_ALL}")
                        
        # Ensure numeric values are properly typed
        if isinstance(data, dict):
            def convert_numeric(value):
                if isinstance(value, dict):
                    return {k: convert_numeric(v) for k, v in value.items()}
                elif isinstance(value, list):
                    return [convert_numeric(item) for item in value]
                elif isinstance(value, str):
                    try:
                        if '.' in value:
                            return float(value)
                        return int(value)
                    except (ValueError, TypeError):
                        return value
                return value
            
            for key in ["Latitude", "Longitude"]:
                if key in data:
                    try:
                        data[key] = float(data[key])
                    except (ValueError, TypeError):
                        pass
                        
            data = convert_numeric(data)
            print(f"{Fore.CYAN}ℹ️ Converted numeric values{Style.RESET_ALL}")
                        
        print(f"{Fore.GREEN}✓ Successfully cleaned and validated response{Style.RESET_ALL}")
        return data

    except Exception as e:
        print(f"{Fore.RED}✗ Unexpected error while cleaning response: {str(e)}{Style.RESET_ALL}")
        return {
            "error": "Unexpected error",
            "details": str(e)
        }