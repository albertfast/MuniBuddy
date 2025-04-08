# # Add parent directory to path
# import os
# import sys
# sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
#
# from sqlalchemy import Column, String, Integer, Float
# from sqlalchemy.orm import Session
# from fastapi import FastAPI, Depends
# from app.db.database import Base, get_db
# from app.config import settings
#
# class BusRoute(Base):
#     __tablename__ = "bus_routes"
#     __table_args__ = {'extend_existing': True}  # Allow table redefinition
#
#     id = Column(Integer, primary_key=True)
#     route_id = Column(String, unique=True)  # the route_id data coming from GTFS
#     line_ref = Column(String)  # The LineRef will be match with API
#     agency_id = Column(String)
#     route_name = Column(String)
#     direction = Column(String)
#     origin = Column(String)
#     destination = Column(String)
#
#     def __repr__(self):
#         return f"<BusRoute {self.route_name} ({self.agency_id})>"
#
# print("[DEBUG] BusRoute model initialized")
#
# # Test code - only runs if this file is run directly
# if __name__ == "__main__":
#     from app.db.database import SessionLocal
#
#     # Create a new session
#     db = SessionLocal()
#     try:
#         # Get first 5 routes
#         routes = db.query(BusRoute).limit(5).all()
#         print("\nFirst 5 routes in database:")
#         for route in routes:
#             print(route)
#     finally:
#         db.close()
