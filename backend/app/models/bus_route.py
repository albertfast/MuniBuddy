from sqlalchemy import Column, String, Integer
from app.db.database import Base

class BusRoute(Base):
    __tablename__ = "bus_routes"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    route_id = Column(String, unique=True)
    line_ref = Column(String)
    agency_id = Column(String)
    route_name = Column(String)
    direction = Column(String)
    origin = Column(String)
    destination = Column(String)

    def __repr__(self):
        return f"<BusRoute {self.route_name} ({self.agency_id})>"