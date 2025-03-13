import pandas as pd

routes = pd.read_csv("gtfs_data/routes.txt", dtype=str)
trips = pd.read_csv("gtfs_data/trips.txt", dtype=str)

print("Routes.txt Column Names: ", routes.columns)
print("Trips.txt Column Names: ", trips.columns)

print(routes.head())
print(trips.head())
