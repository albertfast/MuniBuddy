import pandas as pd
import redis
import json
import os

# Connect to Redis
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

def load_all_gtfs_to_redis(base_dir="/home/asahiner/Projects/MuniBuddy/backend/gtfs_data"):
    """
    Recursively load all GTFS .txt files under the base_dir into Redis.
    Each file is stored as a Redis key: gtfs:{agency}:{filename without .txt}
    """
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".txt"):
                full_path = os.path.join(root, file)
                try:
                    df = pd.read_csv(full_path, dtype=str)
                    agency = os.path.basename(root)
                    redis_key = f"gtfs:{agency}:{file.replace('.txt','')}"
                    data = df.to_dict(orient="records")
                    r.set(redis_key, json.dumps(data))
                    print(f"✔️ Loaded {redis_key} - {len(data)} records")
                except Exception as e:
                    print(f"❌ Failed to load {full_path}: {str(e)}")

# Run loader
load_all_gtfs_to_redis()
