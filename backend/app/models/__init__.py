from sqlalchemy.orm import declarative_base
from .bus_route import BusRoute

Base = declarative_base()

__all__ = ['Base', 'BusRoute']