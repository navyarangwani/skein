"""
Shared Neo4j driver instance for the API. One driver, reused across
requests -- the neo4j driver manages its own connection pool
internally, so creating a new driver per-request would be wasteful
and is explicitly against the driver's own usage guidance.
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.environ["NEO4J_URI"]
USER = os.environ["NEO4J_USER"]
PASSWORD = os.environ["NEO4J_PASSWORD"]

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))


def get_session():
    return driver.session()


def close_driver():
    driver.close()