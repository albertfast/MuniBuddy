from route_finder2 import find_nearest_stop, build_graph, G
from app.database import get_db, SessionLocal
from fastapi.testclient import TestClient
from app.route_api import app  
import logging

# ✅ Logging ayarları
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 📌 Test edilecek adresler
start_address = "628 34th. ave, San Francisco"
end_address = "Fisherman's Wharf, San Francisco"

# 📍 Latitude ve Longitude değerlerini manuel belirledik
start_lat, start_lon = 37.77339229349792, -122.49477444251549  # Örnek: San Francisco koordinatları
end_lat, end_lon = 37.79008002634932, -122.40997372723999  # Örnek: Fisherman's Wharf

# ✅ Veritabanı bağlantısını aç
db = SessionLocal()

try:
    # 📌 En yakın durakları bul
    start_stop = find_nearest_stop(start_lat, start_lon, db)
    end_stop = find_nearest_stop(end_lat, end_lon, db)

    logger.debug(f"Start Stop: {start_stop}, End Stop: {end_stop}")

    # 📌 Grafı oluştur
    build_graph(db)
    logger.debug(f"Graph Nodes: {len(G.nodes)}, Graph Edges: {len(G.edges)}")

except Exception as e:
    logger.error(f"Hata oluştu: {e}")

finally:
    db.close()  # ✅ Veritabanı bağlantısını kapat


client = TestClient(app)

# 📌 API çağrısı ile en kısa rotayı test et
response = client.get("/optimized-route", params={
    "start_lat": 37.733592,
    "start_lon": -122.498572,
    "end_lat": 37.809671,
    "end_lon": -122.476242
})

print(response.json())  # 📌 Yanıtı ekrana yazdır