from app.routers.routers import routes

stations = {
    "ANTC": {"lat": 37.995368, "lng": -121.780374, "name": "Antioch", "iconAbbreviation": "A"},
    "12TH": {"lat": 37.803066, "lng": -122.271588, "name": "12th St. Oakland City Center", "iconAbbreviation": "12"},
    "16TH": {"lat": 37.765214, "lng": -122.419431, "name": "16th St. Mission", "iconAbbreviation": "16"},
    "19TH": {"lat": 37.807593, "lng": -122.268884, "name": "19th St. Oakland", "iconAbbreviation": "19"},
    "24TH": {"lat": 37.752423, "lng": -122.418294, "name": "24th St. Mission", "iconAbbreviation": "24"},
    "ASHB": {"lat": 37.85303, "lng": -122.269957, "name": "Ashby", "iconAbbreviation": "AS"},
    "WARM": {"lat": 37.501974, "lng": -121.93925, "name": "Warm Springs", "iconAbbreviation": "WS"},
    "OAKL": {"lat": 37.713238, "lng": -122.212191, "name": "Oakland International Airport", "iconAbbreviation": "OA"},
}

station_to_lines = {}

for line, info in routes.items():
    for station in info["stations"]:
        station_to_lines.setdefault(station, []).append(line)