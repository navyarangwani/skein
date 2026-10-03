"""
Isolation Forest risk scoring (Section 11).

Trains UNSUPERVISED -- ground_truth.csv is never shown to the model
during fit(). It's only used afterward, here, to check how well the
model's anomaly scores separate known fraud entities from clean ones.
This separation matters: unsupervised doesn't mean "untested", it
means "didn't need labels to train" -- validating against labels we
happen to have is still essential and expected practice.
"""

import os
import pandas as pd
import numpy as np
from neo4j import GraphDatabase
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from dotenv import load_dotenv

load_dotenv()

URI = os.environ["NEO4J_URI"]
USER = os.environ["NEO4J_USER"]
PASSWORD = os.environ["NEO4J_PASSWORD"]

FEATURE_COLUMNS = [
    "pagerank",
    "betweenness",
    "in_cycle",
    "total_sent",
    "total_received",
    "txn_count",
    "avg_amount",
]
def ablation_test(features_df):
    """
    Retrains using ONLY structural/graph features (pagerank, betweenness,
    in_cycle) -- no amount-based features at all. If AUC stays high,
    the model is genuinely learning graph structure, which is the
    harder and more realistic signal. If AUC drops sharply, the full
    model's near-perfect score was mostly just "this entity moved an
    unusually large amount of money" -- a real finding, worth knowing
    honestly rather than discovering it for the first time in an
    interview.
    """
    structural_cols = ["pagerank", "betweenness", "in_cycle"]
    X = features_df[structural_cols].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(n_estimators=200, contamination=0.02, random_state=42)
    model.fit(X_scaled)
    raw_scores = model.decision_function(X_scaled)
    scores = (raw_scores.max() - raw_scores) / (raw_scores.max() - raw_scores.min()) * 100

    gt = pd.read_csv("data/sample_output/ground_truth.csv")[["entity_id", "is_fraud_ring_member"]]
    temp = features_df[["entity_id"]].copy()
    temp["structural_score"] = scores
    merged = temp.merge(gt, on="entity_id", how="left")

    auc = roc_auc_score(merged["is_fraud_ring_member"], merged["structural_score"])
    print(f"\n[Ablation] Structural features only (pagerank, betweenness, in_cycle): ROC-AUC = {auc:.4f}")
    return auc


def extract_features(session):
    """
    Pulls one row per entity: graph-algorithm outputs (pagerank,
    betweenness, in_cycle) plus transaction-volume statistics computed
    directly in Cypher. community_id is deliberately left OUT of the
    numeric feature set -- it's an arbitrary integer label, not a
    magnitude, so feeding it straight into a distance/split-based model
    like Isolation Forest would imply a false ordering (community 50
    isn't "more" of anything than community 2).
    """
    result = session.run("""
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[out:TRANSACTION]->()
        OPTIONAL MATCH (e)<-[inc:TRANSACTION]-()
        WITH e,
             coalesce(sum(out.amount), 0.0) AS total_sent,
             coalesce(sum(inc.amount), 0.0) AS total_received,
             count(DISTINCT out) + count(DISTINCT inc) AS txn_count
        RETURN e.entity_id AS entity_id,
               coalesce(e.pagerank, 0.0) AS pagerank,
               coalesce(e.betweenness, 0.0) AS betweenness,
               coalesce(e.in_cycle, false) AS in_cycle,
               total_sent,
               total_received,
               txn_count
    """)
    df = pd.DataFrame([dict(r) for r in result])
    df["in_cycle"] = df["in_cycle"].astype(int)
    df["avg_amount"] = (df["total_sent"] + df["total_received"]) / df["txn_count"].replace(0, 1)
    return df


def train_isolation_forest(features_df):
    X = features_df[FEATURE_COLUMNS].values

    # Scaling matters here: pagerank/betweenness/amounts live on wildly
    # different numeric scales (pagerank ~0-20, amounts ~0-2,000,000).
    # Isolation Forest splits on raw feature values, so without scaling,
    # amount columns would dominate every split purely due to magnitude,
    # not because they're actually more anomalous.
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=200,
        contamination=0.02,  # ~2% expected anomaly rate -- roughly matches
                              # your known 32-ish fraud entities out of 3000
        random_state=42,
    )
    model.fit(X_scaled)

    # decision_function: higher = more normal, lower/negative = more
    # anomalous. We flip and rescale to 0-100 so "higher score = more
    # suspicious" reads naturally for the dashboard later.
    raw_scores = model.decision_function(X_scaled)
    anomaly_score = (raw_scores.max() - raw_scores) / (raw_scores.max() - raw_scores.min()) * 100

    features_df["anomaly_score"] = anomaly_score
    features_df["is_anomaly"] = model.predict(X_scaled) == -1
    return features_df, model, scaler


def validate_against_ground_truth(features_df, ground_truth_path="data/sample_output/ground_truth.csv"):
    gt = pd.read_csv(ground_truth_path)[["entity_id", "is_fraud_ring_member"]]
    merged = features_df.merge(gt, on="entity_id", how="left")

    auc = roc_auc_score(merged["is_fraud_ring_member"], merged["anomaly_score"])

    top_n = merged.nlargest(50, "anomaly_score")
    precision_at_50 = top_n["is_fraud_ring_member"].sum() / 50

    print(f"ROC-AUC: {auc:.4f}")
    print(f"Precision@50 (top 50 by anomaly score): {precision_at_50:.4f} "
          f"({int(top_n['is_fraud_ring_member'].sum())}/50 are real fraud entities)")
    return auc, precision_at_50


def write_scores_to_neo4j(session, features_df):
    rows = features_df[["entity_id", "anomaly_score", "is_anomaly"]].to_dict("records")
    for i in range(0, len(rows), 1000):
        chunk = rows[i:i + 1000]
        session.run("""
            UNWIND $rows AS row
            MATCH (e:Entity {entity_id: row.entity_id})
            SET e.anomaly_score = row.anomaly_score,
                e.is_anomaly = row.is_anomaly
        """, rows=chunk)
    print(f"Wrote anomaly_score to {len(rows)} entities.")


def main():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        print("Extracting features...")
        features_df = extract_features(session)
        print(f"Extracted {len(features_df)} entities, features: {FEATURE_COLUMNS}")

        print("Training Isolation Forest...")
        features_df, model, scaler = train_isolation_forest(features_df)

        print("\nValidating against ground truth (NOT used during training)...")
        validate_against_ground_truth(features_df)

        print("\nWriting scores back to Neo4j...")
        write_scores_to_neo4j(session, features_df)

    validate_against_ground_truth(features_df)
    ablation_test(features_df)

    driver.close()
    print("\nDone.")


if __name__ == "__main__":
    main()