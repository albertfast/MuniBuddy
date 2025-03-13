import requests

API_KEY = "d11301a5-2cb9-4c4a-ad47-b449ed6794c0"
url = f"http://api.511.org/transit/VehicleMonitoring?api_key={API_KEY}&agency=SF"
url1 = f"http://127.0.0.1:8000/bus-positions?bus_number=5R&agency=SFMTA"


response = requests.get(url)
print(response.text[:500])

response2 = requests.get(url1)
print(response2.text[:500])
