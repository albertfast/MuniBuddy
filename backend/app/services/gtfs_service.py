from typing import Optional, List
import pandas as pd
from sqlalchemy import text
from app.db.database import engine
from app.config import settings


class GTFSService:
    def __init__(self, agency: str = "muni"):
        self.agency = settings.normalize_agency(agency)
        self.prefix = f"{self.agency}_"

    def _query(self, table: str, where: Optional[str] = None, params: Optional[dict] = None) -> pd.DataFrame:
        full_table = f"{self.prefix}{table}"
        query = f"SELECT * FROM {full_table}"
        if where:
            query += f" WHERE {where}"
        return pd.read_sql(text(query), con=engine, params=params)

    def get_routes(self) -> pd.DataFrame:
        return self._query("routes")

    def get_route_by_id(self, route_id: str) -> pd.DataFrame:
        return self._query("routes", "route_id = :route_id", {"route_id": route_id})

    def get_trips_by_route(self, route_id: str) -> pd.DataFrame:
        return self._query("trips", "route_id = :route_id", {"route_id": route_id})

    def get_trip_stop_times(self, trip_id: str) -> pd.DataFrame:
        return self._query("stop_times", "trip_id = :trip_id ORDER BY stop_sequence", {"trip_id": trip_id})

    def get_stops(self) -> pd.DataFrame:
        return self._query("stops")

    def get_stop_by_id(self, stop_id: str) -> pd.DataFrame:
        return self._query("stops", "stop_id = :stop_id", {"stop_id": stop_id})

    def get_stops_for_trip(self, trip_id: str) -> pd.DataFrame:
        query = f"""
            SELECT s.stop_id, s.stop_name, st.arrival_time, st.departure_time, st.stop_sequence
            FROM {self.prefix}stop_times st
            JOIN {self.prefix}stops s ON st.stop_id = s.stop_id
            WHERE st.trip_id = :trip_id
            ORDER BY st.stop_sequence
        """
        return pd.read_sql(text(query), con=engine, params={"trip_id": trip_id})

    def get_shapes_by_trip(self, shape_id: str) -> pd.DataFrame:
        return self._query("shapes", "shape_id = :shape_id ORDER BY shape_pt_sequence", {"shape_id": shape_id})

    def get_calendar(self) -> pd.DataFrame:
        return self._query("calendar")

    def get_calendar_dates(self) -> pd.DataFrame:
        return self._query("calendar_dates")

    def list_tables(self) -> List[str]:
        like_prefix = f"{self.prefix}%"
        query = """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name LIKE :like_prefix
        """
        return pd.read_sql(text(query), con=engine, params={"like_prefix": like_prefix})["table_name"].tolist()
