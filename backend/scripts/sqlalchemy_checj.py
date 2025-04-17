import pandas as pd
from sqlalchemy import text
from app.db.database import engine

query = text("SELECT * FROM bart_routes WHERE route_id = 'Yellow-N'")
df = pd.read_sql(query, con=engine)
print(df)
