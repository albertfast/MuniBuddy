import xml.etree.ElementTree as ET

def xml_to_json(xml_string):
    """Convert XML string to JSON."""
    try:
        root = ET.fromstring(xml_string)
        return {root.tag: {child.tag: child.text for child in root}}
    except ET.ParseError:
        print("Error parsing XML response")
        return {}
