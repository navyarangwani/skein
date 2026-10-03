"""
Neo4j schema setup: constraints + indexes.
Run once (idempotent — safe to re-run) before loading data.
"""

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

URI = os.environ["NEO4J_URI"]
USER = os.environ["NEO4J_USER"]
PASSWORD = os.environ["NEO4J_PASSWORD"]


def setup_schema(driver):
    with driver.session() as session:
        # Uniqueness constraint on entity_id — also auto-creates an index on it,
        # which is what makes every MERGE (e:Entity {entity_id: ...}) fast
        # instead of a full label scan.
        session.run("""
            CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
            FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE
        """)
        session.run("""
            CREATE CONSTRAINT transaction_id_unique IF NOT EXISTS
            FOR ()-[t:TRANSACTION]-() REQUIRE t.transaction_id IS UNIQUE
        """)
        print("Schema constraints created (or already existed).")


if __name__ == "__main__":
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    setup_schema(driver)
    driver.close()