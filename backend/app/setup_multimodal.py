# setup_multimodal.py

import pandas as pd
import requests
from sqlalchemy import create_engine, text
from datetime import datetime, time
from typing import List, Dict
import logging
import json
from app.database import SessionLocal
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_multimodal_tables(db):
    """Create necessary tables for multimodal transit"""
    try:
        # Create BART stations table
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS bart_stations (
                station_id VARCHAR(50) PRIMARY KEY,
                station_name VARCHAR(100),
                latitude FLOAT,
                longitude FLOAT,
                wheelchair_accessible BOOLEAN DEFAULT true,
                elevator_available BOOLEAN DEFAULT true,
                parking_available BOOLEAN DEFAULT false,
                bike_parking_available BOOLEAN DEFAULT false
            );
        """))
        
        # Create transfer points table
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS transfer_points (
                stop_id VARCHAR(50),
                bart_station_id VARCHAR(50),
                transfer_type VARCHAR(20),
                min_transfer_time INTEGER,
                wheelchair_path BOOLEAN DEFAULT true,
                covered_waiting_area BOOLEAN DEFAULT false,
                distance_feet INTEGER,
                PRIMARY KEY (stop_id, bart_station_id)
            );
        """))
        
        # Create peak hours table
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS peak_hours (
                id SERIAL PRIMARY KEY,
                day_of_week INTEGER,
                start_time TIME,
                end_time TIME,
                delay_factor FLOAT,
                route_type VARCHAR(20)
            );
        """))
        
        # Create weather impacts table
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS weather_impacts (
                id SERIAL PRIMARY KEY,
                condition VARCHAR(20),
                severity INTEGER,
                delay_factor FLOAT,
                route_type VARCHAR(20),
                active BOOLEAN DEFAULT true
            );
        """))
        
        # Create route delays table
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS route_delays (
                id SERIAL PRIMARY KEY,
                route_id VARCHAR(50),
                delay_minutes FLOAT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        db.commit()
        logger.info("Created multimodal tables successfully")
        
    except Exception as e:
        logger.error(f"Error creating multimodal tables: {e}")
        db.rollback()
        raise

def setup_database():
    """Initialize database tables and load initial data"""
    try:
        db = SessionLocal()
        
        # Create tables
        create_multimodal_tables(db)
        logger.info("Created multimodal tables successfully")
        
        # Load BART stations
        load_bart_stations(db)
        logger.info("Loaded BART stations successfully")
        
        # Load transfer points
        load_transfer_points(db)
        logger.info("Loaded transfer points successfully")
        
        # Load peak hours
        load_peak_hours(db)
        logger.info("Loaded peak hours successfully")
        
        # Load weather impact data
        load_weather_impacts(db)
        logger.info("Loaded weather impacts successfully")
        
        db.commit()
        logger.info("Database setup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during database setup: {e}")
        raise
    finally:
        db.close()

def load_bart_stations(db):
    """Load BART station data from official API"""
    try:
        # BART API endpoint for station list
        url = "https://api.bart.gov/api/stn.aspx?cmd=stns&key=MW9S-E7SL-26DU-VV8V&json=y"
        response = requests.get(url)
        data = response.json()
        
        stations = data['root']['stations']['station']
        
        for station in stations:
            db.execute(text("""
                INSERT INTO bart_stations (
                    station_id,
                    station_name,
                    latitude,
                    longitude,
                    wheelchair_accessible,
                    elevator_available,
                    parking_available,
                    bike_parking_available
                ) VALUES (
                    :station_id,
                    :name,
                    :latitude,
                    :longitude,
                    :wheelchair,
                    :elevator,
                    :parking,
                    :bike
                ) ON CONFLICT (station_id) DO UPDATE SET
                    station_name = EXCLUDED.station_name,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude
            """), {
                "station_id": f"BART_{station['abbr']}",
                "name": station['name'],
                "latitude": float(station['gtfs_latitude']),
                "longitude": float(station['gtfs_longitude']),
                "wheelchair": True,  # Default values
                "elevator": True,
                "parking": False,  # Default values
                "bike": False
            })
        
        logger.info(f"Loaded {len(stations)} BART stations")
        
    except Exception as e:
        logger.error(f"Error loading BART stations: {e}")
        raise

def load_transfer_points(db):
    """Load transfer points between BART and bus stops"""
    # Define maximum walking distance for transfers (in feet)
    MAX_TRANSFER_DISTANCE = 1320  # Quarter mile
    
    try:
        # Get all BART stations
        bart_stations = db.execute(text("SELECT * FROM bart_stations")).fetchall()
        
        # Get all bus stops
        bus_stops = db.execute(text("SELECT * FROM stops")).fetchall()
        
        for station in bart_stations:
            station_point = (station.latitude, station.longitude)
            
            # Find nearby bus stops
            for stop in bus_stops:
                stop_point = (stop.stop_lat, stop.stop_lon)
                distance = calculate_distance(station_point, stop_point)
                
                if distance <= MAX_TRANSFER_DISTANCE:
                    # Calculate walking time (assuming 3.1 mph walking speed)
                    walking_time = int((distance / 5280) * (60 / 3.1))
                    
                    db.execute(text("""
                        INSERT INTO transfer_points (
                            stop_id,
                            bart_station_id,
                            transfer_type,
                            min_transfer_time,
                            wheelchair_path,
                            covered_waiting_area,
                            distance_feet
                        ) VALUES (
                            :stop_id,
                            :station_id,
                            :transfer_type,
                            :transfer_time,
                            :wheelchair,
                            :covered,
                            :distance
                        ) ON CONFLICT (stop_id, bart_station_id) DO UPDATE SET
                            min_transfer_time = EXCLUDED.min_transfer_time,
                            distance_feet = EXCLUDED.distance_feet
                    """), {
                        "stop_id": stop.stop_id,
                        "station_id": station.station_id,
                        "transfer_type": "bus_to_bart",
                        "transfer_time": walking_time,
                        "wheelchair": True,  # Default values
                        "covered": False,
                        "distance": int(distance)
                    })
        
        logger.info("Transfer points loaded successfully")
        
    except Exception as e:
        logger.error(f"Error loading transfer points: {e}")
        raise

def load_peak_hours(db):
    """Load peak hours data"""
    peak_hours_data = [
        # Weekday morning peak
        {"day": day, "start": "07:00", "end": "10:00", "factor": 1.3, "type": "all"}
        for day in range(0, 5)  # Monday to Friday
    ] + [
        # Weekday evening peak
        {"day": day, "start": "16:00", "end": "19:00", "factor": 1.3, "type": "all"}
        for day in range(0, 5)  # Monday to Friday
    ]
    
    try:
        for peak in peak_hours_data:
            db.execute(text("""
                INSERT INTO peak_hours (
                    day_of_week,
                    start_time,
                    end_time,
                    delay_factor,
                    route_type
                ) VALUES (
                    :day,
                    :start,
                    :end,
                    :factor,
                    :type
                )
            """), peak)
        
        logger.info("Peak hours data loaded successfully")
        
    except Exception as e:
        logger.error(f"Error loading peak hours: {e}")
        raise

def load_weather_impacts(db):
    """Load weather impact data"""
    weather_impacts = [
        {"condition": "rain", "severity": 1, "factor": 1.1, "type": "all"},
        {"condition": "rain", "severity": 2, "factor": 1.2, "type": "all"},
        {"condition": "rain", "severity": 3, "factor": 1.4, "type": "all"},
        {"condition": "fog", "severity": 1, "factor": 1.1, "type": "all"},
        {"condition": "fog", "severity": 2, "factor": 1.3, "type": "all"},
        {"condition": "wind", "severity": 1, "factor": 1.1, "type": "all"},
        {"condition": "wind", "severity": 2, "factor": 1.2, "type": "all"},
        {"condition": "wind", "severity": 3, "factor": 1.5, "type": "all"}
    ]
    
    try:
        for impact in weather_impacts:
            db.execute(text("""
                INSERT INTO weather_impacts (
                    condition,
                    severity,
                    delay_factor,
                    route_type,
                    active
                ) VALUES (
                    :condition,
                    :severity,
                    :factor,
                    :type,
                    true
                )
            """), impact)
        
        logger.info("Weather impacts data loaded successfully")
        
    except Exception as e:
        logger.error(f"Error loading weather impacts: {e}")
        raise

def calculate_distance(point1, point2):
    """Calculate distance between two points in feet"""
    from math import sin, cos, sqrt, atan2, radians
    
    R = 20902231  # Earth radius in feet
    
    lat1, lon1 = map(radians, point1)
    lat2, lon2 = map(radians, point2)
    
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distance = R * c
    return distance

if __name__ == "__main__":
    setup_database()