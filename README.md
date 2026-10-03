# Skein

**A real-time, graph-based financial crime network detector.**

Skein treats financial crime detection as a graph problem. Instead of analyzing transactions as isolated rows, it models relationships between entities, transactions, communities, and transaction cycles to identify structural patterns associated with money laundering.

It combines **Neo4j Graph Data Science**, **FastAPI**, **React**, **Redis Streams**, and **unsupervised machine learning** to detect suspicious transaction networks and surface them through an investigator-focused dashboard.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python\&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-5-008CC1?logo=neo4j\&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi\&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react\&logoColor=black)
![Redis](https://img.shields.io/badge/Redis-Streams-DC382D?logo=redis\&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker\&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Overview

Traditional transaction-based fraud detection often treats each transaction independently. This can miss the relationships that make financial crime suspicious.

Skein models financial activity as a **property graph**, allowing it to reason about:

* Transaction cycles and closed-loop flows
* High-centrality entities
* Dense transaction communities
* Suspicious pass-through entities
* Smurfing-style fan-out patterns
* Structural anomalies across transaction networks

The system combines deterministic graph analysis with unsupervised anomaly detection to produce risk scores and expose the underlying transaction relationships behind suspicious entities.

---

## Key Capabilities

### Graph-Based Transaction Modeling

Financial entities and transactions are represented as a graph in **Neo4j**.

This makes relationships first-class analytical objects rather than simply columns in a transaction table.

### Layering & Cycle Detection

Skein searches for bounded transaction cycles that can represent circular movement of funds.

The system supports:

* Per-transaction cycle checks
* Periodic full graph cycle scans
* Bounded path traversal for predictable performance

### Graph Data Science

Neo4j Graph Data Science algorithms are used to extract structural features including:

* **PageRank**
* **Betweenness Centrality**
* **Louvain Community Detection**
* **Cycle Participation**

These features capture how entities behave within the wider transaction network.

### Unsupervised Risk Scoring

Skein uses an **Isolation Forest** to identify structurally anomalous entities without requiring a labeled fraud dataset.

The model incorporates graph-derived features alongside transaction characteristics to produce an anomaly-based risk score.

### Investigator-Focused Dashboard

The React dashboard presents suspicious entities in an investigation-oriented interface, including:

* Risk-ranked entities
* Transaction relationships
* Graph context
* Entity-level details
* Supporting transaction activity

The goal is not just to flag an entity, but to make the **reason behind the flag inspectable**.

---

## Architecture

```text
                         Transaction Stream
                                │
                                ▼
                    ┌──────────────────────┐
                    │    Redis Streams     │
                    │   Live Event Feed    │
                    └──────────┬───────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │             Neo4j               │
              │       Graph + GDS Layer         │
              │                                │
              │  ┌────────────┐ ┌────────────┐ │
              │  │ Speed Layer│ │ Batch Layer│ │
              │  │            │ │            │ │
              │  │ Per-event  │ │ PageRank   │ │
              │  │ cycle      │ │ Louvain    │ │
              │  │ detection  │ │ Betweenness│ │
              │  └────────────┘ │ Cycle scan │ │
              │                 └────────────┘ │
              └───────────────┬────────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │    Feature Extraction  │
                  │                        │
                  │ PageRank               │
                  │ Betweenness            │
                  │ Community              │
                  │ Cycle participation    │
                  └────────────┬───────────┘
                               │
                               ▼
                  ┌────────────────────────┐
                  │    Isolation Forest    │
                  │  Unsupervised Anomaly  │
                  │       Detection        │
                  └────────────┬───────────┘
                               │
                               ▼
                  ┌────────────────────────┐
                  │      FastAPI API       │
                  └────────────┬───────────┘
                               │
                               ▼
                  ┌────────────────────────┐
                  │    React Dashboard     │
                  │                        │
                  │ Risk Ledger             │
                  │ Entity Dossiers         │
                  │ Transaction Context     │
                  └────────────────────────┘
```

---

## Detection Approach

Skein uses two complementary analytical layers.

### 1. Deterministic Graph Detection

Known structural patterns are detected directly from the graph.

For example, a transaction sequence such as:

```text
Entity A
   │
   ▼
Entity B
   │
   ▼
Entity C
   │
   ▼
Entity A
```

forms a closed transaction cycle.

Bounded graph traversal is used to identify these patterns while controlling query complexity.

### 2. Unsupervised Anomaly Detection

Graph and transaction features are passed into an Isolation Forest model.

Example feature set:

```text
PageRank
Betweenness Centrality
Community Membership
Cycle Participation
Transaction Amount
Transaction Frequency
```

Because the model is unsupervised, it does not require a pre-labeled fraud dataset to identify unusual entities.

---

## Validated Results

Skein was evaluated using a synthetic AML dataset containing approximately **3,000 entities and 15,150 transactions**, with deliberately injected suspicious structures including layering rings, smurfing clusters, and pass-through hubs.

| Metric                                      |                        Result |
| ------------------------------------------- | ----------------------------: |
| Isolation Forest ROC-AUC — Full Feature Set |                    **0.9963** |
| ROC-AUC — Structural Features Only          |                    **0.9535** |
| Precision@50                                |                   **27 / 50** |
| Known Fraud Entities Recovered @50          |                   **27 / 32** |
| Speed-Layer Cycle Detection Target          | **< 5 seconds / transaction** |

### Structural Feature Ablation

The structural-only model achieved a **0.9535 ROC-AUC** without relying on transaction amount data.

This provides evidence that graph topology itself carries substantial discriminatory information in the synthetic evaluation dataset.

---

## Technology Stack

### Backend

* **Python 3.11**
* **FastAPI**
* **scikit-learn**
* **NetworkX**
* **Neo4j Python Driver**

### Graph & Data

* **Neo4j 5**
* **Neo4j Graph Data Science**
* **Cypher**
* **Redis Streams**

### Frontend

* **React**
* **Vite**

### Infrastructure

* **Docker**
* **Docker Compose**

---

## Project Structure

```text
skein/
│
├── backend/
│   │
│   ├── api/
│   │   └── FastAPI backend
│   │
│   ├── data_generator/
│   │   └── Synthetic AML dataset generation
│   │
│   ├── graph/
│   │   ├── Neo4j schema
│   │   ├── Graph loader
│   │   └── Graph algorithms
│   │
│   ├── ml/
│   │   └── Isolation Forest risk scoring
│   │
│   └── streaming/
│       └── Redis Streams producer / consumer
│
├── frontend/
│   └── React + Vite dashboard
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites

Make sure the following are installed:

* [Docker](https://www.docker.com/)
* [Python 3.11](https://www.python.org/)
* [Node.js](https://nodejs.org/)
* npm

---

### 1. Clone the Repository

```bash
git clone https://github.com/navyarangwani/skein.git
cd skein
```

---

### 2. Start Infrastructure

Start Neo4j and Redis using Docker Compose:

```bash
docker compose up -d
```

Verify that the containers are running:

```bash
docker compose ps
```

---

### 3. Set Up the Backend

Navigate to the backend:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

Activate it on macOS/Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

### 4. Configure Environment Variables

Create a `.env` file inside `backend/`.

Example:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

REDIS_HOST=localhost
REDIS_PORT=6379
```

> Never commit `.env` files or credentials to Git.

---

### 5. Generate Synthetic Data

From the `backend` directory:

```bash
python -m data_generator.generate_synthetic_data
```

---

### 6. Initialize the Graph

Create the Neo4j schema:

```bash
python -m graph.schema
```

Load the generated transaction data:

```bash
python -m graph.loader
```

---

### 7. Run Graph Algorithms

```bash
python -m graph.algorithms
```

This calculates the graph-derived features used by the risk-scoring pipeline.

---

### 8. Train the Risk Model

```bash
python -m ml.risk_scoring
```

This trains the Isolation Forest model and generates anomaly-based risk scores.

---

### 9. Start the FastAPI Backend

```bash
uvicorn api.main:app --reload --port 8000
```

API:

http://localhost:8000

Interactive API documentation:

http://localhost:8000/docs

---

### 10. Start the Frontend

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be available at:

http://localhost:5173

---

## Graph Model

The core graph represents financial entities and their transactions.

A simplified representation is:

```text
(:Entity)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(:Entity)
```

The graph can then be queried to understand:

* Who transacted with whom?
* Which entities form tightly connected communities?
* Which entities sit between many other entities?
* Which entities participate in transaction cycles?
* Which entities exhibit unusual structural behavior?

This allows suspicious activity to be analyzed in its network context rather than as isolated transactions.

---

## Risk Scoring

The risk pipeline combines graph-derived structural signals with transaction-level information.

Conceptually:

```text
Transaction Data
       │
       ▼
Neo4j Graph
       │
       ├── PageRank
       ├── Betweenness Centrality
       ├── Louvain Communities
       └── Cycle Participation
       │
       ▼
Feature Matrix
       │
       ▼
Isolation Forest
       │
       ▼
Anomaly / Risk Score
       │
       ▼
Investigator Dashboard
```

The use of an unsupervised model is intentional: real-world AML systems may face limited availability of reliable, labeled fraud data.

---

## Why Graphs?

Financial crime networks are rarely isolated events.

A suspicious transaction may only become meaningful when viewed alongside:

* The sender and recipient
* Previous and subsequent transactions
* Shared counterparties
* Community membership
* Centrality within the network
* Circular transaction paths

Graph representations make these relationships explicit.

For example:

```text
             ┌──────────────┐
             │   Entity A   │
             └──────┬───────┘
                    │
                    ▼
             ┌──────────────┐
             │   Entity B   │
             └──────┬───────┘
                    │
                    ▼
             ┌──────────────┐
             │   Entity C   │
             └──────┬───────┘
                    │
                    └──────────────► Entity A
```

A flat transaction table can represent these transactions individually. A graph can represent the **relationship between all of them simultaneously**.

---

## Performance Design

Skein separates transaction-time detection from heavier graph analytics.

### Speed Layer

The speed layer focuses on event-level operations such as:

* Updating the graph
* Checking newly introduced transaction paths
* Detecting bounded cycles

The target latency for the cycle-detection path is **under 5 seconds per transaction**.

### Batch Layer

More computationally expensive operations are handled separately, including:

* PageRank
* Betweenness Centrality
* Louvain community detection
* Full graph cycle scans
* Risk model retraining

This separation prevents expensive graph analytics from blocking transaction ingestion.

---

## Synthetic Data

The project uses a controlled synthetic dataset for development and evaluation.

The generator creates normal transaction activity and injects specific suspicious structures, including:

* Layering rings
* Smurfing-style clusters
* Pass-through hubs

The background transaction graph is generated to avoid unintended cycles, allowing injected cycles to be evaluated as known suspicious structures rather than accidental artifacts of random graph generation.

---

## Limitations

Skein is a research and portfolio prototype rather than a production AML compliance platform.

Current limitations include:

* The evaluation dataset is synthetic rather than real banking data.
* Detection performance on real-world financial data may differ substantially.
* The batch cycle scan uses a bounded path length, with a default maximum of 6 hops, to control computational cost.
* The Isolation Forest model is retrained from scratch for each run.
* The current real-time streaming layer is still under active development.
* The risk score should be treated as an analytical signal, not as a definitive determination of financial crime.

---

## Future Work

Potential extensions include:

* Persistent model serving and incremental retraining
* More sophisticated temporal graph features
* Temporal community detection
* Graph neural networks for representation learning
* Entity resolution across accounts and organizations
* Explainable risk scoring
* Configurable investigator alert thresholds
* Real-time alert prioritization
* Case management and investigation workflows
* Historical risk-score tracking
* Integration with external sanctions and watchlist data
* Production-scale stream processing

---

## API

The FastAPI service exposes the backend functionality required by the dashboard.

Once the backend is running, interactive API documentation is available through Swagger UI:

**[Open API Documentation](http://localhost:8000/docs)**

For local development, the API runs on:

```text
http://localhost:8000
```

---

## Dashboard

The frontend is designed around an investigator workflow rather than exposing raw machine-learning outputs.

The intended flow is:

```text
Risk-ranked entity
        │
        ▼
Entity investigation
        │
        ▼
Transaction relationships
        │
        ▼
Graph context
        │
        ▼
Suspicious pattern
        │
        ▼
Investigation decision
```

This makes the system's output more interpretable than presenting anomaly scores alone.

---

## Development

To stop the local infrastructure:

```bash
docker compose down
```

To stop containers and remove their associated volumes:

```bash
docker compose down -v
```

> Use the volume-removal command carefully because it can delete local Neo4j data.

---

## Security

Never commit:

```text
.env
credentials
API keys
private certificates
production database credentials
generated sensitive datasets
```

The repository's `.gitignore` should exclude local secrets and generated development artifacts.

---

## Disclaimer

Skein is an educational and research-oriented prototype demonstrating graph analytics, anomaly detection, streaming architecture, and financial crime investigation workflows.

It is **not** a certified AML compliance system and should not be used as the sole basis for real-world financial crime investigations, regulatory reporting, account restrictions, or other consequential decisions.

---

## License

This project is licensed under the **MIT License**.

---

## Author

### Navya Rangwani

Computer Engineering student focused on:

* Artificial Intelligence
* Graph-based systems
* Agentic architectures
* Machine Learning
* Full-Stack Development

**GitHub:** [@navyarangwani](https://github.com/navyarangwani)

**Project:** [Skein](https://github.com/navyarangwani/skein)

---

<p align="center">
  Built with Neo4j, FastAPI, React, Redis, and Python.
</p>
