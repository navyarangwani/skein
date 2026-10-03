"""
Skein synthetic dataset generator.
Produces entities.csv, transactions.csv, ownership.csv, ground_truth.csv
per Section 13.1 of the spec.
"""

import random
import uuid
from datetime import datetime, timedelta

import networkx as nx
import pandas as pd
from faker import Faker

fake = Faker()
random.seed(42)

N_ENTITIES = 3000
N_TRANSACTIONS = 15000
START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 12, 31)

ENTITY_TYPE_WEIGHTS = {"individual": 0.70, "company": 0.25, "shell_company": 0.05}

N_RINGS = 4
N_SMURF_CLUSTERS = 2
N_HUBS = 2
N_HUB_TXNS_PER_SIDE = 20


def random_timestamp():
    delta = END_DATE - START_DATE
    seconds = random.randint(0, int(delta.total_seconds()))
    return START_DATE + timedelta(seconds=seconds)


def make_entity_id(i):
    return f"ENT_{i:05d}"


def generate_entities(n=N_ENTITIES):
    entities = []
    types = list(ENTITY_TYPE_WEIGHTS.keys())
    weights = list(ENTITY_TYPE_WEIGHTS.values())

    for i in range(n):
        etype = random.choices(types, weights=weights, k=1)[0]
        if etype == "individual":
            name = fake.name()
        elif etype == "company":
            name = fake.company()
        else:
            name = f"{fake.word().capitalize()} {random.choice(['Holdings', 'Trading', 'Ventures', 'Capital', 'Group'])} {random.choice(['LLC', 'Ltd', 'Inc'])}"

        entities.append({
            "entity_id": make_entity_id(i),
            "name": name,
            "entity_type": etype,
            "kyc_flag": random.choices([0, 1], weights=[0.9, 0.1], k=1)[0],
            "created_at": random_timestamp().isoformat(),
        })
    return pd.DataFrame(entities)


def build_global_rank(entities_df):
    """
    Assigns one global rank to every entity. Any edge oriented
    low-rank -> high-rank can never be part of a cycle -- a cycle would
    require rank to strictly increase all the way around and still
    return to where it started, which is impossible. Used to orient
    the background graph (making it provably acyclic) and to double-
    constrain the hub pattern's direction.
    """
    ids = entities_df["entity_id"].tolist()
    shuffled = ids.copy()
    random.shuffle(shuffled)
    return {eid: i for i, eid in enumerate(shuffled)}


def select_fraud_participants(entities_df):
    """
    Pre-selects every entity that will participate in an injected fraud
    pattern (ring member, smurf source, hub) BEFORE the background
    graph is built, so these entities can be excluded from it entirely.

    WHY THIS MATTERS: earlier versions built the background graph over
    ALL entities, including fraud participants, then layered fraud
    edges on top. Fraud edges necessarily violate the background's
    rank ordering (that's what makes them fraud-shaped) -- so in a
    dense, small-world graph like this one, a single fraud edge could
    almost always be completed into an accidental short loop by an
    ordinary background path, with zero fraud meaning. Testing
    confirmed this directly: 45 distinct entities showed up across all
    detected cycles, but only 16 were genuine fraud entities -- 29 were
    innocent background entities pulled in by chance.

    THE FIX: fraud participants get ZERO background edges. Their only
    connections are the deliberate fraud-pattern edges. This also
    happens to match a real AML red flag -- genuinely isolated shell
    companies with no organic economic activity outside the suspicious
    pattern -- so it's a realism improvement, not just a technical fix.
    """
    shell_ids = entities_df[entities_df["entity_type"] == "shell_company"]["entity_id"].tolist()
    all_ids = entities_df["entity_id"].tolist()

    available_shells = shell_ids.copy()
    random.shuffle(available_shells)

    ring_assignments = []
    for _ in range(N_RINGS):
        ring_size = random.randint(5, 10)
        if len(available_shells) < ring_size:
            break
        members = available_shells[:ring_size]
        available_shells = available_shells[ring_size:]
        ring_assignments.append(members)

    used_ids = {eid for ring in ring_assignments for eid in ring}

    available_others = [e for e in all_ids if e not in used_ids]
    random.shuffle(available_others)
    smurf_sources = available_others[:N_SMURF_CLUSTERS]
    used_ids.update(smurf_sources)

    available_shells_for_hub = [e for e in available_shells if e not in used_ids]
    hubs = available_shells_for_hub[:N_HUBS]
    used_ids.update(hubs)

    return {
        "ring_assignments": ring_assignments,
        "smurf_sources": smurf_sources,
        "hubs": hubs,
        "excluded_ids": used_ids,
    }


def generate_background_graph(entities_df, n_transactions, rank, excluded_ids):
    """
    Barabási–Albert scale-free graph as the 'normal' transaction
    background. Built ONLY over entities not involved in any injected
    fraud pattern (see select_fraud_participants) -- this keeps fraud
    entities structurally isolated from the background, so the batch
    cycle scan (Section 10.6) can only ever find the cycles deliberately
    injected below.

    Edges are oriented by global rank (always low-rank -> high-rank),
    which independently makes the background graph provably acyclic on
    its own, as a second layer of protection.
    """
    normal_ids = [e for e in entities_df["entity_id"].tolist() if e not in excluded_ids]
    n = len(normal_ids)
    m = max(1, round(n_transactions / n))
    ba_graph = nx.barabasi_albert_graph(n, m=m, seed=42)

    ordered_ids = sorted(normal_ids, key=lambda eid: rank[eid])

    edges = list(ba_graph.edges())
    random.shuffle(edges)

    directed_edges = []
    for u, v in edges:
        a, b = ordered_ids[u], ordered_ids[v]
        src, dst = (a, b) if rank[a] < rank[b] else (b, a)
        directed_edges.append((src, dst))

    transactions = []
    i = 0
    while len(transactions) < n_transactions and directed_edges:
        src, dst = directed_edges[i % len(directed_edges)]
        i += 1
        transactions.append({
            "transaction_id": str(uuid.uuid4()),
            "source_entity_id": src,
            "destination_entity_id": dst,
            "amount": round(random.lognormvariate(8, 1.2), 2),
            "currency": "INR",
            "timestamp": random_timestamp(),
            "transaction_type": random.choice(["transfer", "payment", "wire"]),
        })

    return transactions


def inject_layering_rings(ring_assignments):
    """
    Circular layering rings: 5-10 shell entities, amount decays 85-95%
    per hop, closing back to the origin. This is what Section 10.6/10.7's
    cycle detection is specifically built to catch. Ring members have no
    background edges (see select_fraud_participants), so the ONLY
    cycles these entities can ever form are their own intended rings.
    """
    ring_transactions = []
    ground_truth_rows = []

    for ring_num, ring_members in enumerate(ring_assignments):
        ring_size = len(ring_members)
        starting_amount = round(random.uniform(500000, 2000000), 2)
        amount = starting_amount
        decay = random.uniform(0.85, 0.95)
        base_time = random_timestamp()

        for hop in range(ring_size):
            src = ring_members[hop]
            dst = ring_members[(hop + 1) % ring_size]
            ring_transactions.append({
                "transaction_id": str(uuid.uuid4()),
                "source_entity_id": src,
                "destination_entity_id": dst,
                "amount": round(amount, 2),
                "currency": "INR",
                "timestamp": base_time + timedelta(hours=hop * random.randint(1, 6)),
                "transaction_type": "wire",
            })
            amount *= decay

        for eid in ring_members:
            ground_truth_rows.append({
                "entity_id": eid,
                "is_fraud_ring_member": 1,
                "pattern_type": "layering",
                "ring_id": f"RING_{ring_num}",
            })

    return ring_transactions, ground_truth_rows


def inject_smurfing_clusters(entities_df, smurf_sources, excluded_ids):
    """
    Smurfing: one source splits a large sum into 15-30 small outgoing
    transactions, each just under a reporting threshold. Targets are
    drawn only from entities outside the fraud-participant set. The
    source itself has no background edges at all (see
    select_fraud_participants), so no path can ever loop back to it --
    this pattern can no longer accidentally close a cycle regardless of
    which targets are picked.
    """
    all_ids = entities_df["entity_id"].tolist()
    eligible_targets = [e for e in all_ids if e not in excluded_ids]
    smurf_transactions = []
    ground_truth_rows = []
    REPORTING_THRESHOLD = 200000

    for cluster_num, source in enumerate(smurf_sources):
        n_splits = random.randint(15, 30)
        targets = random.sample(eligible_targets, min(n_splits, len(eligible_targets)))
        base_time = random_timestamp()

        for i, target in enumerate(targets):
            amount = REPORTING_THRESHOLD * random.uniform(0.85, 0.98)
            smurf_transactions.append({
                "transaction_id": str(uuid.uuid4()),
                "source_entity_id": source,
                "destination_entity_id": target,
                "amount": round(amount, 2),
                "currency": "INR",
                "timestamp": base_time + timedelta(minutes=i * random.randint(5, 60)),
                "transaction_type": "transfer",
            })

        ground_truth_rows.append({
            "entity_id": source,
            "is_fraud_ring_member": 1,
            "pattern_type": "smurfing",
            "ring_id": f"SMURF_{cluster_num}",
        })

    return smurf_transactions, ground_truth_rows


def inject_hub_shell_entities(entities_df, hubs, rank, excluded_ids, n_txns_per_side=N_HUB_TXNS_PER_SIDE):
    """
    1-2 artificial hub/shell entities (Section 13.1): a single entity
    that touches a disproportionate share of total volume by acting as
    a pass-through. Senders/receivers are drawn only from entities
    outside the fraud-participant set, AND constrained so senders have
    lower rank than the hub and receivers have higher rank -- two
    independent safeguards against this pattern accidentally closing a
    loop with the background.
    """
    all_ids = entities_df["entity_id"].tolist()
    eligible = [e for e in all_ids if e not in excluded_ids]
    hub_transactions = []
    ground_truth_rows = []

    for hub in hubs:
        hub_rank = rank[hub]
        lower = [e for e in eligible if rank[e] < hub_rank]
        higher = [e for e in eligible if rank[e] > hub_rank]

        sources = random.sample(lower, min(n_txns_per_side, len(lower)))
        destinations = random.sample(higher, min(n_txns_per_side, len(higher)))
        base_time = random_timestamp()

        for i, src in enumerate(sources):
            hub_transactions.append({
                "transaction_id": str(uuid.uuid4()),
                "source_entity_id": src,
                "destination_entity_id": hub,
                "amount": round(random.uniform(50000, 300000), 2),
                "currency": "INR",
                "timestamp": base_time + timedelta(hours=i),
                "transaction_type": "transfer",
            })

        for i, dst in enumerate(destinations):
            hub_transactions.append({
                "transaction_id": str(uuid.uuid4()),
                "source_entity_id": hub,
                "destination_entity_id": dst,
                "amount": round(random.uniform(50000, 300000), 2),
                "currency": "INR",
                "timestamp": base_time + timedelta(hours=i, minutes=30),
                "transaction_type": "transfer",
            })

        ground_truth_rows.append({
            "entity_id": hub,
            "is_fraud_ring_member": 1,
            "pattern_type": "hub_shell",
            "ring_id": f"HUB_{hub}",
        })

    return hub_transactions, ground_truth_rows


def generate_ownership(entities_df):
    """
    Lightweight ownership edges: some companies/shells are 'owned' by
    individuals or other companies.
    """
    companies = entities_df[entities_df["entity_type"].isin(["company", "shell_company"])]
    individuals = entities_df[entities_df["entity_type"] == "individual"]

    rows = []
    for _, company in companies.iterrows():
        if random.random() < 0.6 and len(individuals) > 0:
            owner = individuals.sample(1).iloc[0]
            rows.append({
                "owner_entity_id": owner["entity_id"],
                "owned_entity_id": company["entity_id"],
                "ownership_pct": round(random.uniform(20, 100), 1),
            })
    return pd.DataFrame(rows)


def main():
    print("Generating entities...")
    entities_df = generate_entities()

    print("Computing global entity rank...")
    rank = build_global_rank(entities_df)

    print("Selecting fraud participants (isolating them from the background graph)...")
    participants = select_fraud_participants(entities_df)
    excluded_ids = participants["excluded_ids"]

    print("Generating background transaction graph...")
    background_txns = generate_background_graph(entities_df, N_TRANSACTIONS, rank, excluded_ids)

    print("Injecting layering rings...")
    ring_txns, ring_gt = inject_layering_rings(participants["ring_assignments"])

    print("Injecting smurfing clusters...")
    smurf_txns, smurf_gt = inject_smurfing_clusters(entities_df, participants["smurf_sources"], excluded_ids)

    print("Injecting hub/shell entities...")
    hub_txns, hub_gt = inject_hub_shell_entities(entities_df, participants["hubs"], rank, excluded_ids)

    all_txns = background_txns + ring_txns + smurf_txns + hub_txns
    transactions_df = pd.DataFrame(all_txns).sort_values("timestamp").reset_index(drop=True)

    ground_truth_df = pd.DataFrame(ring_gt + smurf_gt + hub_gt)
    flagged_ids = set(ground_truth_df["entity_id"]) if not ground_truth_df.empty else set()
    clean_rows = [
        {"entity_id": eid, "is_fraud_ring_member": 0, "pattern_type": None, "ring_id": None}
        for eid in entities_df["entity_id"] if eid not in flagged_ids
    ]
    ground_truth_df = pd.concat([ground_truth_df, pd.DataFrame(clean_rows)], ignore_index=True)
    ground_truth_df = ground_truth_df.drop_duplicates(subset="entity_id", keep="first")

    ownership_df = generate_ownership(entities_df)

    out_dir = "data/sample_output"
    entities_df.to_csv(f"{out_dir}/entities.csv", index=False)
    transactions_df.to_csv(f"{out_dir}/transactions.csv", index=False)
    ownership_df.to_csv(f"{out_dir}/ownership.csv", index=False)
    ground_truth_df.to_csv(f"{out_dir}/ground_truth.csv", index=False)

    print(f"\nDone.")
    print(f"  entities.csv:      {len(entities_df)} rows")
    print(f"  transactions.csv:  {len(transactions_df)} rows")
    print(f"  ownership.csv:     {len(ownership_df)} rows")
    print(f"  ground_truth.csv:  {len(ground_truth_df)} rows ({len(flagged_ids)} flagged)")


if __name__ == "__main__":
    main()