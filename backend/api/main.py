"""
Skein API -- FastAPI backend serving entity risk data, transaction
history, and detected fraud cycles from Neo4j.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .db import get_session, close_driver
from .schemas import EntitySummary, TransactionOut, CycleOut, StatsOut

app = FastAPI(title="Skein API", version="0.1.0")

# CORS: the Day 6 React dev server runs on a different port
# (typically :5173 or :3000), so without this, browser requests from
# the frontend to this API would be blocked by same-origin policy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
def shutdown():
    close_driver()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats", response_model=StatsOut)
def get_stats():
    with get_session() as session:
        result = session.run("""
            MATCH (e:Entity)
            RETURN count(e) AS total_entities,
                   count(CASE WHEN e.is_anomaly THEN 1 END) AS total_anomalies,
                   count(CASE WHEN e.in_cycle THEN 1 END) AS total_in_cycle,
                   count(DISTINCT e.community_id) AS community_count
        """).single()

        txn_count = session.run("""
            MATCH ()-[t:TRANSACTION]->() RETURN count(t) AS total_transactions
        """).single()["total_transactions"]

        return StatsOut(
            total_entities=result["total_entities"],
            total_transactions=txn_count,
            total_anomalies=result["total_anomalies"],
            total_in_cycle=result["total_in_cycle"],
            community_count=result["community_count"],
        )


@app.get("/entities", response_model=list[EntitySummary])
def list_entities(
    limit: int = Query(50, le=500),
    sort_by: str = Query("anomaly_score", pattern="^(anomaly_score|pagerank|betweenness)$"),
    anomalies_only: bool = False,
):
    where_clause = "WHERE e.is_anomaly = true" if anomalies_only else ""
    query = f"""
        MATCH (e:Entity)
        {where_clause}
        RETURN e.entity_id AS entity_id, e.name AS name, e.entity_type AS entity_type,
               coalesce(e.pagerank, 0.0) AS pagerank,
               coalesce(e.betweenness, 0.0) AS betweenness,
               e.community_id AS community_id,
               coalesce(e.in_cycle, false) AS in_cycle,
               coalesce(e.anomaly_score, 0.0) AS anomaly_score,
               coalesce(e.is_anomaly, false) AS is_anomaly
        ORDER BY e.{sort_by} DESC
        LIMIT $limit
    """
    with get_session() as session:
        result = session.run(query, limit=limit)
        return [EntitySummary(**dict(r)) for r in result]


@app.get("/entities/{entity_id}", response_model=EntitySummary)
def get_entity(entity_id: str):
    with get_session() as session:
        result = session.run("""
            MATCH (e:Entity {entity_id: $entity_id})
            RETURN e.entity_id AS entity_id, e.name AS name, e.entity_type AS entity_type,
                   coalesce(e.pagerank, 0.0) AS pagerank,
                   coalesce(e.betweenness, 0.0) AS betweenness,
                   e.community_id AS community_id,
                   coalesce(e.in_cycle, false) AS in_cycle,
                   coalesce(e.anomaly_score, 0.0) AS anomaly_score,
                   coalesce(e.is_anomaly, false) AS is_anomaly
        """, entity_id=entity_id).single()

        if result is None:
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
        return EntitySummary(**dict(result))


@app.get("/entities/{entity_id}/transactions", response_model=list[TransactionOut])
def get_entity_transactions(entity_id: str, limit: int = Query(50, le=500)):
    with get_session() as session:
        result = session.run("""
            MATCH (e:Entity {entity_id: $entity_id})-[t:TRANSACTION]-(other:Entity)
            RETURN t.transaction_id AS transaction_id,
                   CASE WHEN startNode(t) = e THEN e.entity_id ELSE other.entity_id END AS source_entity_id,
                   CASE WHEN startNode(t) = e THEN other.entity_id ELSE e.entity_id END AS destination_entity_id,
                   t.amount AS amount, t.currency AS currency,
                   toString(t.timestamp) AS timestamp, t.transaction_type AS transaction_type
            ORDER BY t.timestamp DESC
            LIMIT $limit
        """, entity_id=entity_id, limit=limit)
        return [TransactionOut(**dict(r)) for r in result]


@app.get("/cycles", response_model=list[CycleOut])
def get_cycles(max_length: int = Query(6, le=10), limit: int = Query(100, le=500)):
    with get_session() as session:
        result = session.run(f"""
            MATCH path = (a:Entity)-[:TRANSACTION*2..{max_length}]->(a)
            RETURN [n IN nodes(path) | n.entity_id] AS cycle_entities,
                   length(path) AS cycle_length,
                   reduce(total = 0.0, r IN relationships(path) | total + r.amount) AS total_volume
            LIMIT $limit
        """, limit=limit)
        return [CycleOut(**dict(r)) for r in result]