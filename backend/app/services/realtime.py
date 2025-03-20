from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, List, Optional
from datetime import datetime
import logging
import requests
from app.config import settings

logger = logging.getLogger(__name__)

def get_realtime_delays(db: Session) -> Dict[str, float]:
    """Get real-time delays for all routes"""
    try:
        # Get delays from 511 API
        delays = get_511_delays()
        
        # Store delays in database for historical tracking
        store_delays(delays, db)
        
        return delays
        
    except Exception as e:
        logger.error(f"Error getting real-time delays: {str(e)}")
        return {}

def get_511_delays() -> Dict[str, float]:
    """Get delays from 511 API"""
    try:
        url = f"http://api.511.org/transit/VehicleMonitoring?api_key={settings.API_KEY}&agency=SF"
        response = requests.get(url)
        
        if response.status_code != 200:
            logger.error(f"511 API error: {response.status_code}")
            return {}
            
        # Clean UTF-8-BOM character
        text = response.text.encode().decode('utf-8-sig')
        data = json.loads(text)
        
        delays = {}
        vehicles = data.get("Siri", {}).get("ServiceDelivery", {}).get("VehicleMonitoringDelivery", [{}])[0].get("VehicleActivity", [])
        
        for vehicle in vehicles:
            route_id = vehicle.get("MonitoredVehicleJourney", {}).get("LineRef", "")
            delay = vehicle.get("MonitoredVehicleJourney", {}).get("Delay", 0)
            delays[route_id] = float(delay)
        
        logger.info(f"Retrieved delays for {len(delays)} routes")
        return delays
        
    except Exception as e:
        logger.error(f"Error fetching 511 delays: {str(e)}")
        return {}

def store_delays(delays: Dict[str, float], db: Session):
    """Store delays in database for historical tracking"""
    try:
        current_time = datetime.now()
        
        for route_id, delay in delays.items():
            db.execute(text("""
                INSERT INTO route_delays (
                    route_id,
                    delay_minutes,
                    timestamp
                ) VALUES (
                    :route_id,
                    :delay,
                    :timestamp
                );
            """), {
                "route_id": route_id,
                "delay": delay,
                "timestamp": current_time
            })
        
        db.commit()
        logger.info(f"Stored {len(delays)} delays in database")
        
    except Exception as e:
        logger.error(f"Error storing delays: {str(e)}")
        db.rollback()

def get_route_realtime_data(route_id: str, db: Session) -> Dict:
    """Get real-time data for a specific route"""
    try:
        # Get current delays
        delays = get_realtime_delays(db)
        current_delay = delays.get(route_id, 0)
        
        # Get vehicle positions
        vehicles = get_route_vehicles(route_id)
        
        return {
            "route_id": route_id,
            "current_delay": current_delay,
            "vehicles": vehicles,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting route real-time data: {str(e)}")
        raise

def get_route_vehicles(route_id: str) -> List[Dict]:
    """Get vehicle positions for a specific route"""
    try:
        url = f"http://api.511.org/transit/VehicleMonitoring?api_key={settings.API_KEY}&agency=SF&route={route_id}"
        response = requests.get(url)
        
        if response.status_code != 200:
            logger.error(f"511 API error: {response.status_code}")
            return []
            
        text = response.text.encode().decode('utf-8-sig')
        data = json.loads(text)
        
        vehicles = []
        for vehicle in data.get("Siri", {}).get("ServiceDelivery", {}).get("VehicleMonitoringDelivery", [{}])[0].get("VehicleActivity", []):
            journey = vehicle.get("MonitoredVehicleJourney", {})
            vehicles.append({
                "vehicle_id": journey.get("VehicleRef", ""),
                "lat": float(journey.get("VehicleLocation", {}).get("Latitude", 0)),
                "lon": float(journey.get("VehicleLocation", {}).get("Longitude", 0)),
                "heading": float(journey.get("Bearing", 0)),
                "speed": float(journey.get("Speed", 0)),
                "delay": float(journey.get("Delay", 0))
            })
        
        return vehicles
        
    except Exception as e:
        logger.error(f"Error getting route vehicles: {str(e)}")
        return [] 