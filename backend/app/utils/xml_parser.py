import xml.etree.ElementTree as ET
import xmltodict
import json
from typing import Dict, Any

def xml_to_json(xml_string: str) -> Dict[str, Any]:
    """
    Converts XML string to JSON format using xmltodict.
    Falls back to ElementTree if xmltodict fails.
    
    Args:
        xml_string (str): XML string to convert
        
    Returns:
        dict: Converted JSON data
        
    Raises:
        ValueError: If XML parsing fails
    """
    try:
        # Try xmltodict first
        data_dict = xmltodict.parse(xml_string)
        return json.loads(json.dumps(data_dict))
    except Exception as e:
        try:
            # Fallback to ElementTree
            root = ET.fromstring(xml_string)
            return {root.tag: {child.tag: child.text for child in root}}
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XML: {str(e)}")