"""
Runs Neo4j GDS algorithms (Louvain, PageRank, Betweenness) on a
named in-memory graph projection, writes results back as node
properties, then drops the projection to free memory.
Also runs the full cycle scan (Cypher, not GDS).
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.environ["NEO4J_URI"]
USER = os.environ["NEO4J_USER"]
PASSWORD = os.environ["NEO4J_PASSWORD"]

GRAPH_NAME = "skeinGraph"


def drop_projection_if_exists(session):
    session.run(f"""
        CALL gds.graph.exists('{GRAPH_NAME}') YIELD exists
        WHERE exists
        CALL gds.graph.drop('{GRAPH_NAME}') YIELD graphName
        RETURN graphName
    """)


def create_projection(session):
    session.run("""
        CALL gds.graph.project(
            $graphName,
            'Entity',
            'TRANSACTION',
            { relationshipProperties: 'amount' }
        )
    """, graphName=GRAPH_NAME)
    print(f"Projection '{GRAPH_NAME}' created.")


def run_louvain(session):
    result = session.run(f"""
        CALL gds.louvain.write('{GRAPH_NAME}', {{
            writeProperty: 'community_id',
            relationshipWeightProperty: 'amount'
        }})
        YIELD communityCount, modularity
        RETURN communityCount, modularity
    """).single()
    print(f"Louvain: {result['communityCount']} communities, modularity={result['modularity']:.4f}")


def run_pagerank(session):
    result = session.run(f"""
        CALL gds.pageRank.write('{GRAPH_NAME}', {{
            writeProperty: 'pagerank',
            relationshipWeightProperty: 'amount'
        }})
        YIELD nodePropertiesWritten
        RETURN nodePropertiesWritten
    """).single()
    print(f"PageRank: {result['nodePropertiesWritten']} node properties written.")


def run_betweenness(session):
    result = session.run(f"""
        CALL gds.betweenness.write('{GRAPH_NAME}', {{
            writeProperty: 'betweenness'
        }})
        YIELD nodePropertiesWritten
        RETURN nodePropertiesWritten
    """).single()
    print(f"Betweenness: {result['nodePropertiesWritten']} node properties written.")


def run_full_cycle_scan(session, max_length=6, limit=500):
    """
    Full cycle scan (Section 10.6). This is the expensive, batch-only
    version — it finds ALL simple cycles up to max_length, unlike the
    incremental per-edge check we'll build in Phase 2.
    """
    result = session.run(f"""
        MATCH path = (a:Entity)-[:TRANSACTION*2..{max_length}]->(a)
        RETURN [n IN nodes(path) | n.entity_id] AS cycle_entities,
               reduce(total = 0.0, r IN relationships(path) | total + r.amount) AS total_volume,
               length(path) AS cycle_length
        LIMIT {limit}
    """)
    cycles = [dict(record) for record in result]
    print(f"Full cycle scan: {len(cycles)} cycles found (limit={limit}).")
    return cycles


def run_batch_analysis():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        drop_projection_if_exists(session)
        create_projection(session)

        run_louvain(session)
        run_pagerank(session)
        run_betweenness(session)

        drop_projection_if_exists(session)  # free the in-memory projection

        cycles = run_full_cycle_scan(session)

    driver.close()
    return cycles


if __name__ == "__main__":
    run_batch_analysis()