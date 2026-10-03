"""
Transaction producer: replays transactions.csv onto a Redis Stream,
simulating a live feed. In production this would be a real payment
system publishing events; here, we're standing in for that so the
speed-layer consumer (Day 8) and batch/model layers (Day 9+) have
something real to react to.
"""

import os
import time
import json
import pandas as pd
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
STREAM_NAME = "skein:transactions"

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def produce(csv_path="data/sample_output/transactions.csv", delay_seconds=0.05, limit=None):
    df = pd.read_csv(csv_path).sort_values("timestamp")
    if limit:
        df = df.head(limit)

    print(f"Producing {len(df)} transactions to stream '{STREAM_NAME}'...")
    for i, row in df.iterrows():
        event = {
            "transaction_id": row["transaction_id"],
            "source_entity_id": row["source_entity_id"],
            "destination_entity_id": row["destination_entity_id"],
            "amount": str(row["amount"]),
            "currency": row["currency"],
            "timestamp": str(row["timestamp"]),
            "transaction_type": row["transaction_type"],
        }
        r.xadd(STREAM_NAME, event)

        if i % 500 == 0:
            print(f"  ...produced {i}/{len(df)}")

        time.sleep(delay_seconds)  # throttle so the consumer can keep up and it LOOKS live

    print("Done producing.")


if __name__ == "__main__":
    # delay_seconds=0.05 -> ~20 txns/sec. limit=500 keeps a demo run short;
    # remove limit to replay everything (~15,000 txns, ~12.5 min at this rate).
    produce(delay_seconds=0.05, limit=500)