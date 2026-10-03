"""
Batch loader: CSV -> Neo4j.
Uses MERGE everywhere so re-running this script is always safe
(idempotent) even if some entities/transactions already exist.
"""

import os
import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.environ["NEO4J_URI"]
USER = os.environ["NEO4J_USER"]
PASSWORD = os.environ["NEO4J_PASSWORD"]

DATA_DIR = "data/sample_output"
BATCH_SIZE = 1000  # load in chunks so one transaction doesn't hold the whole dataset


def load_entities(session, entities_df):
    rows = entities_df.to_dict("records")
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i:i + BATCH_SIZE]
        session.run("""
            UNWIND $rows AS row
            MERGE (e:Entity {entity_id: row.entity_id})
            SET e.name = row.name,
                e.entity_type = row.entity_type,
                e.kyc_flag = toInteger(row.kyc_flag),
                e.created_at = row.created_at
        """, rows=chunk)
    print(f"Loaded {len(rows)} entities.")


def load_transactions(session, transactions_df):
    rows = transactions_df.to_dict("records")
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i:i + BATCH_SIZE]
        session.run("""
            UNWIND $rows AS row
            MATCH (src:Entity {entity_id: row.source_entity_id})
            MATCH (dst:Entity {entity_id: row.destination_entity_id})
            MERGE (src)-[t:TRANSACTION {transaction_id: row.transaction_id}]->(dst)
            SET t.amount = toFloat(row.amount),
                t.currency = row.currency,
                t.timestamp = row.timestamp,
                t.transaction_type = row.transaction_type
        """, rows=chunk)
        print(f"  ...loaded {min(i + BATCH_SIZE, len(rows))}/{len(rows)} transactions")
    print(f"Loaded {len(rows)} transactions.")


def load_ownership(session, ownership_df):
    if ownership_df.empty:
        print("No ownership rows to load.")
        return
    rows = ownership_df.to_dict("records")
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i:i + BATCH_SIZE]
        session.run("""
            UNWIND $rows AS row
            MATCH (owner:Entity {entity_id: row.owner_entity_id})
            MATCH (owned:Entity {entity_id: row.owned_entity_id})
            MERGE (owner)-[o:OWNS]->(owned)
            SET o.ownership_pct = toFloat(row.ownership_pct)
        """, rows=chunk)
    print(f"Loaded {len(rows)} ownership edges.")


def main():
    entities_df = pd.read_csv(f"{DATA_DIR}/entities.csv")
    transactions_df = pd.read_csv(f"{DATA_DIR}/transactions.csv")
    ownership_df = pd.read_csv(f"{DATA_DIR}/ownership.csv")

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        load_entities(session, entities_df)
        load_transactions(session, transactions_df)
        load_ownership(session, ownership_df)
    driver.close()
    print("\nBatch load complete.")


if __name__ == "__main__":
    main()
    