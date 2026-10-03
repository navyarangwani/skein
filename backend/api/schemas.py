"""
Pydantic response models -- these define the API's actual contract.
FastAPI uses these to validate outgoing data AND auto-generate the
OpenAPI docs at /docs, so keeping them accurate matters beyond just
type-checking.
"""

from pydantic import BaseModel
from typing import Optional


class EntitySummary(BaseModel):
    entity_id: str
    name: str
    entity_type: str
    pagerank: float
    betweenness: float
    community_id: Optional[int] = None
    in_cycle: bool
    anomaly_score: float
    is_anomaly: bool


class TransactionOut(BaseModel):
    transaction_id: str
    source_entity_id: str
    destination_entity_id: str
    amount: float
    currency: str
    timestamp: str
    transaction_type: str


class CycleOut(BaseModel):
    cycle_entities: list[str]
    cycle_length: int
    total_volume: float


class StatsOut(BaseModel):
    total_entities: int
    total_transactions: int
    total_anomalies: int
    total_in_cycle: int
    community_count: int

    