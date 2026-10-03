Good instinct — a strong README matters a lot for a portfolio project a recruiter will skim in 30 seconds. Let's do this properly: get it on GitHub cleanly first, then make the README actually earn attention.

## Step 1 — Clean up `.gitignore` before anything gets committed

Open `.gitignore` in the `skein` root and make sure it covers everything that shouldn't be pushed (secrets, generated junk, dependencies):

```
venv/
__pycache__/
*.pyc
.env
node_modules/
dist/
backend/data/sample_output/*.csv
neo4j_data/
frontend/.vite/
.DS_Store
```

**Important:** your `backend\.env` has real Neo4j credentials in it — even though they're just local dev defaults (`skein_dev_password`), never commit a `.env` file out of habit. Confirm it's listed above (it already was in your original `.gitignore`), and double check it actually exists before your first commit:

```powershell
cd C:\Users\Navya Rangwani\skein
Get-Content .gitignore
```

## Step 2 — Create the GitHub repo

Go to **https://github.com/new** in your browser:
- Repository name: `skein`
- Description: `Real-time graph-based AML detection system — Neo4j, FastAPI, React`
- Keep it **Public** (recruiters need to see it without logging in)
- **Do NOT** check "Add a README" or "Add .gitignore" — you already have both locally, and GitHub will refuse to push if the remote has commits yours doesn't

Click **Create repository**. On the next page, copy the URL it gives you under "…or push an existing repository from the command line" — it'll look like:
```
https://github.com/navyarangwani/skein.git
```

## Step 3 — Replace your README

Delete whatever's currently in `README.md` at the `skein` root and paste this in full:

```markdown
# Skein

**A real-time, graph-based financial crime network detector.**

Skein models financial transactions as a graph, not a spreadsheet — because money laundering *is* a graph problem. It detects closed-loop layering rings, smurfing fan-outs, and shell-company pass-through hubs using Neo4j graph algorithms and an unsupervised anomaly model, then serves findings through a live dashboard built for investigators, not data scientists.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-5-008CC1?logo=neo4j&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![Redis](https://img.shields.io/badge/Redis-Streams-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Why this exists

Most fraud-detection demos either (a) run a classifier on a flat transaction table and call it a day, or (b) draw a pretty graph with no actual analytical engine behind it. Skein tries to do neither: it's built on the premise that laundering patterns — layering rings, smurfing, pass-through shells — are fundamentally **structural**, and the right tool for structural problems is a graph database with real graph algorithms, not a dataframe with extra steps.

## What it actually does

- **Models** entities and transactions as a property graph in Neo4j
- **Detects** closed transaction cycles (layering) via bounded Cypher path queries — both a live, per-transaction check (<5s) and a periodic full batch scan
- **Scores risk** with an unsupervised Isolation Forest trained on PageRank, Betweenness Centrality, Louvain community membership, and cycle participation — no labels required
- **Streams** live transactions through Redis, updating the graph and re-checking for cycles in real time
- **Serves** everything through a FastAPI backend and a React dashboard built around an investigation-first UI: a sortable risk ledger and a per-entity "dossier" showing the actual transaction thread behind a score

## Architecture

```
┌─────────────────────┐
│  Transaction Stream   │  (Redis Streams — simulated live feed)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│              Neo4j (+ GDS)                │
│  ┌────────────┐  ┌────────────────────┐  │
│  │ Speed layer│  │   Batch layer        │  │
│  │ per-event  │  │   every 500txn/60s   │  │
│  │ bounded    │  │   Louvain, PageRank, │  │
│  │ cycle check│  │   Betweenness, full  │  │
│  │  (<5s)     │  │   cycle scan          │  │
│  └────────────┘  └──────────┬───────────┘  │
└─────────────────────────────┼──────────────┘
                               ▼
                   ┌────────────────────────┐
                   │  Isolation Forest       │
                   │  (unsupervised risk     │
                   │   scoring)              │
                   └───────────┬────────────┘
                               ▼
                   ┌────────────────────────┐
                   │   FastAPI backend       │
                   └───────────┬────────────┘
                               ▼
                   ┌────────────────────────┐
                   │   React dashboard       │
                   └────────────────────────┘
```

## Validated results

Tested on a synthetic dataset (3,000 entities, ~15,150 transactions) with deliberately injected layering rings, smurfing clusters, and pass-through hubs — generated with a provably acyclic background graph so every detected cycle is a genuine fraud pattern, not generator noise.

| Metric | Result |
|---|---|
| Isolation Forest ROC-AUC (full feature set) | **0.9963** |
| ROC-AUC, structural features only (no amount data) | **0.9535** |
| Precision@50 | 27/50 (recovers 27 of 32 known fraud entities) |
| Cycle detection latency (speed layer) | < 5s per transaction (NFR target) |

The structural-only ablation matters: it confirms the model is learning actual graph topology (who's in a cycle, who's structurally central) rather than just flagging "moved a lot of money" — a meaningfully harder and more realistic signal.

## Tech stack

**Graph & data:** Neo4j 5 + Graph Data Science library · Redis Streams
**Backend:** Python, FastAPI, scikit-learn (Isolation Forest), NetworkX (synthetic data generation)
**Frontend:** React (Vite)
**Infra:** Docker Compose

## Quick start

```bash
# 1. Start Neo4j + Redis
docker compose up -d

# 2. Python environment
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 3. Generate data, load graph, run algorithms, train risk model
python -m data_generator.generate_synthetic_data
python -m graph.schema
python -m graph.loader
python -m graph.algorithms
python -m ml.risk_scoring

# 4. Start the API
uvicorn api.main:app --reload --port 8000
# → http://localhost:8000/docs

# 5. Start the frontend (new terminal)
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

## Project structure

```
skein/
├── backend/
│   ├── data_generator/   # Synthetic AML dataset generator
│   ├── graph/            # Neo4j schema, loader, GDS algorithms
│   ├── ml/                # Isolation Forest risk scoring
│   ├── streaming/        # Redis Streams producer/consumer (speed layer)
│   └── api/               # FastAPI backend
├── frontend/              # React dashboard
└── docker-compose.yml
```

## Known limitations

- The batch cycle scan caps path length at 6 hops by default — a deliberate performance tradeoff (see `graph/algorithms.py`)
- Isolation Forest is retrained from scratch each run; `random_state=42` keeps results consistent across runs on the same dataset

## Status

Core detection pipeline (data generation → graph algorithms → risk scoring → API → dashboard) is complete and validated end-to-end. Real-time streaming layer (Redis Streams, live cycle detection) in active development.

---

Built by [Navya Rangwani](https://github.com/navyarangwani) as a portfolio project.
```
