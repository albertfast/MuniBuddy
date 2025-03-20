from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from app.schemas.transit import StopDetail
import logging

logger = logging.getLogger(__name__)

def find_nearest_stops(
    lat: float,
    lon: float,
    radius_miles: float,
    db: Session,
    transit_type: Optional[str] = None
) -> List[StopDetail]:
    """Find nearest transit stops within radius"""
    try:
        logger.info(f"Finding stops near ({lat}, {lon}) within {radius_miles} miles")
        
        # Convert miles to meters (1 mile = 1609.34 meters)
        radius_meters = radius_miles * 1609.34
        
        query = text("""
            WITH nearby_stops AS (
                SELECT 
                    s.stop_id,
                    s.stop_name,
                    s.stop_lat,
                    s.stop_lon,
                    s.wheelchair_accessible,
                    s.covered_waiting_area,
                    ST_Distance(
                        s.geog::geography,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                    ) as distance
                FROM stops s
                WHERE ST_DWithin(
                    s.geog::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius
                )
                ORDER BY distance
                LIMIT 10
            )
            SELECT * FROM nearby_stops;
        """)
        
        results = db.execute(query, {
            "lat": lat,
            "lon": lon,
            "radius": radius_meters
        }).fetchall()
        
        stops = []
        for row in results:
            stop = StopDetail(
                stop_id=row.stop_id,
                stop_name=row.stop_name,
                stop_lat=row.stop_lat,
                stop_lon=row.stop_lon,
                wheelchair_accessible=row.wheelchair_accessible,
                covered_waiting_area=row.covered_waiting_area,
                transit_type="bus"  # Default to bus, will be updated for BART stations
            )
            stops.append(stop)
        
        # If transit_type is specified, filter stops
        if transit_type:
            stops = [s for s in stops if s.transit_type == transit_type]
        
        logger.info(f"Found {len(stops)} stops")
        return stops
        
    except Exception as e:
        logger.error(f"Error finding nearest stops: {str(e)}")
        raise

def find_stops_in_radius(
    lat: float,
    lon: float,
    radius: float,
    transit_type: Optional[str] = None,
    db: Session = None
) -> List[StopDetail]:
    """Find all stops within radius"""
    return find_nearest_stops(lat, lon, radius, db, transit_type)

def get_stop_details(stop_id: str, db: Session) -> Optional[StopDetail]:
    """Get detailed information about a specific stop"""
    try:
        query = text("""
            SELECT 
                s.stop_id,
                s.stop_name,
                s.stop_lat,
                s.stop_lon,
                s.wheelchair_accessible,
                s.covered_waiting_area,
                CASE 
                    WHEN bs.station_id IS NOT NULL THEN 'bart'
                    ELSE 'bus'
                END as transit_type
            FROM stops s
            LEFT JOIN bart_stations bs ON s.stop_id = bs.station_id
            WHERE s.stop_id = :stop_id;
        """)
        
        result = db.execute(query, {"stop_id": stop_id}).fetchone()
        
        if result:
            return StopDetail(
                stop_id=result.stop_id,
                stop_name=result.stop_name,
                stop_lat=result.stop_lat,
                stop_lon=result.stop_lon,
                wheelchair_accessible=result.wheelchair_accessible,
                covered_waiting_area=result.covered_waiting_area,
                transit_type=result.transit_type
            )
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting stop details: {str(e)}")
        raise 