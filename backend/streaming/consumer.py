"""
Speed-layer consumer (Section 8, NFR1: <5s per event).

For each incoming transaction:
  1. MERGE it into Neo4j (same idempotent pattern as the Day 2 batch loader).
  2. Run a BOUNDED path check: does a path already exist from the
     transaction's destination back to its source? If so, this new
     edge just closed a cycle -- flag it immediately, rather than
     waiting for the next full batch scan (which only runs every
     500 txns / 60s, per Section 8's three-speed design).

This is deliberately NOT the same query as Day 3's full cycle scan.
That scan searches from every node in the graph; this one searches
from exactly one node (the new transaction's destination), bounded to
a few hops, which is why it can stay fast enough to run on every
single event instead of periodically.
"""

import os
import time
import json
from neo4j import GraphDatabase
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

STREAM_NAME = "skein:transactions"
CONSUMER_GROUP = "skein-speed-layer"
CONSUMER_NAME = "speed-worker-1"
MAX_CYCLE_HOPS = 6

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def ensure_consumer_group():
    try:
        r.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
        print(f"Created consumer group '{CONSUMER_GROUP}'.")
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"Consumer group '{CONSUMER_GROUP}' already exists, reusing it.")
        else:
            raise


def merge_transaction(session, event):
    session.run("""
        MERGE (src:Entity {entity_id: $source_entity_id})
        MERGE (dst:Entity {entity_id: $destination_entity_id})
        MERGE (src)-[t:TRANSACTION {transaction_id: $transaction_id}]->(dst)
        SET t.amount = toFloat($amount),
            t.currency = $currency,
            t.timestamp = $timestamp,
            t.transaction_type = $transaction_type
    """, **event)


def check_cycle_closed(session, event):
    """
    Bounded check: starting ONLY from the destination of this new edge,
    does a path exist back to the source within MAX_CYCLE_HOPS? If yes,
    this transaction just closed a cycle.
    """
    result = session.run(f"""
        MATCH (dst:Entity {{entity_id: $destination_entity_id}})
        MATCH (src:Entity {{entity_id: $source_entity_id}})
        MATCH path = (dst)-[:TRANSACTION*1..{MAX_CYCLE_HOPS - 1}]->(src)
        RETURN [n IN nodes(path) | n.entity_id] AS cycle_entities LIMIT 1
    """, source_entity_id=event["source_entity_id"], destination_entity_id=event["destination_entity_id"])

    record = result.single()
    return record["cycle_entities"] if record else None


def process_event(session, event):
    start = time.time()
    merge_transaction(session, event)
    cycle = check_cycle_closed(session, event)
    elapsed = time.time() - start

    if cycle:
        full_cycle = cycle + [event["source_entity_id"]]
        print(f"⚠ CYCLE CLOSED ({elapsed*1000:.0f}ms): {' -> '.join(full_cycle)}")
    else:
        print(f"  ok ({elapsed*1000:.0f}ms): {event['source_entity_id']} -> {event['destination_entity_id']}")


def run_consumer():
    ensure_consumer_group()
    print("Listening for transactions... (Ctrl+C to stop)\n")

    with driver.session() as session:
        while True:
            messages = r.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME,
                {STREAM_NAME: ">"},
                count=1, block=2000,
            )
            if not messages:
                continue

            for stream_name, events in messages:
                for event_id, event_data in events:
                    process_event(session, event_data)
                    r.xack(STREAM_NAME, CONSUMER_GROUP, event_id)


if __name__ == "__main__":
    try:
        run_consumer()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        driver.close()