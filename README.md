# Propgatics GenAI Operations Assistant

A production-style AI platform that lets users ask natural-language questions
over the **Propgatics Logistics Intelligence Platform** — 100,000 shipment
records and 25,000 incident records — through a single chat interface that
automatically routes each question to the right agent.

## Why this exists

The Propgatics platform generates rich operational data (shipments, incidents,
carrier performance, route risk scores) across five carriers and ten Canadian
cities. This assistant adds an AI intelligence layer on top: instead of writing
SQL or navigating dashboards, a user can ask "Which routes have the most
critical delays?" or "What does our carrier SLA policy say?" and get a grounded,
cited answer in seconds.

## Architecture

```
                    ┌──────────────────────────┐
   POST /api/chat → │       RouterAgent         │  (confidence-aware classifier)
                    └──────┬───────┬────────────┘
                           │       │ fan-out when confidence < 0.55
          ┌────────────────┼───────┼────────────────┐
          ▼                ▼       ▼                 ▼
  ┌───────────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────────────┐
  │ KnowledgeAgent│ │ SQLAgent │ │AnalyticsAgent│ │ConversationAgent │
  │  (RAG + BM25) │ │ (NL2SQL) │ │(SQL+narrate) │ │   (general Q&A)  │
  └───────┬───────┘ └────┬─────┘ └──────┬───────┘ └──────────────────┘
          ▼              ▼               ▼
   Vector store      SQLite DB       SQLite DB
 (Chroma/in-memory)  shipments       shipments
                      incidents       incidents
```

* **RouterAgent** (`app/agents/router_agent.py`) — confidence-aware
  multi-agent orchestration. Parses LLM confidence score; fans out to a
  secondary agent when confidence < 0.55 and merges both answers.
* **KnowledgeAgent** (`app/agents/knowledge_agent.py`) — two-stage RAG:
  wide vector recall → BM25-lite lexical rerank → relevance floor → grounded
  answer with cited source chunks. Idempotent ingest (delete-before-add).
* **SQLAgent** (`app/agents/sql_agent.py`) — NL2SQL against the full
  Propgatics schema (shipments + incidents tables). Safety gate rejects
  anything that isn't a single read-only `SELECT`.
* **AnalyticsAgent** (`app/agents/analytics_agent.py`) — keyword-dispatched
  analytics (KPI summary, carrier analysis, delay hotspots, risk breakdown,
  weather impact, trend analysis) with LLM-narrated insights.
* **ConversationAgent** — general-purpose fallback for conversational queries.
* **LLMClient** (`app/core/llm_client.py`) — single seam for
  OpenAI/Anthropic, with a deterministic offline `mock` mode so tests and
  CI need zero API keys.
* **FastAPI** (`app/api/main.py`) — `/api/chat`, `/api/sql`, `/api/upload`,
  `/api/health`, `/api/stats`.
* **React + TypeScript** (`frontend/`) — single-page chat UI with mobile
  support, query history, and ambiguous-routing indicator.
* **SQLite** via SQLAlchemy (`app/db/`) — `shipments` (28 columns) and
  `incidents` (19 columns) tables seeded from Propgatics sample CSVs.

Every module's docstring explains the underlying concept (chunking,
embeddings, tokens/context window, tool calling, confidence thresholds,
reranking, CI/CD) — read those inline as interview prep.

## Data: Propgatics Logistics Intelligence Platform

The backend is seeded from the Propgatics dataset (`data/shipments_sample.csv`,
`data/incidents_sample.csv`):

| Dataset   | Sample (seeded) | Full Propgatics dataset |
|-----------|-----------------|-------------------------|
| Shipments | 5,000 rows      | 100,000 rows            |
| Incidents | 1,000 rows      | 25,000 rows             |

**Carriers:** UPS, FedEx, DHL, Canada Post, Purolator  
**Cities:** Toronto, Vancouver, Calgary, Montreal, Edmonton, Halifax, Moncton, Kelowna, Ottawa, Winnipeg  
**Shipment statuses:** Delivered, Minor Delay, Delayed, Critical Delay  
**KPIs (full dataset):** 75.26% on-time · 2.52 h avg delay · CAD $7.43M revenue · CAD $18.86M delivery cost

Route distances (`distance_km`, `estimated_duration_hours`) were generated via
the OpenRouteService API against real Canadian city coordinates.

## Running it

**Fastest path (no Docker, no API key):**

```bash
pip install -r requirements.txt
cp .env.example .env                 # LLM_PROVIDER=mock by default
python -m app.db.seed                # seeds Propgatics sample data into SQLite
uvicorn app.api.main:app --reload
# in another terminal:
cd frontend && npm install && npm run dev
```

Open the frontend and try:
- "What is the on-time delivery rate by carrier?" → AnalyticsAgent (SQL+narrate)
- "Show all Critical Delay shipments from Toronto" → SQLAgent (NL2SQL)
- "What does the carrier SLA policy say?" → KnowledgeAgent (RAG)
- "Which routes have the highest risk scores?" → AnalyticsAgent or SQLAgent (fan-out)

**Full stack with Docker:**

```bash
docker compose up --build
docker compose exec backend python -m app.db.seed
```

**Going live with a real model:** set `LLM_PROVIDER=openai` (or `anthropic`)
and the matching API key in `.env` — no code changes needed.

## Tests

```bash
pytest -v
```

Tests use `LLM_PROVIDER=mock` — zero network calls, zero API keys, same as CI
(`.github/workflows/ci.yml`).

## What's deliberately scoped down (and why)

- **Embeddings**: a hand-rolled hashing-trick embedder (`app/rag/embeddings.py`)
  instead of OpenAI's embedding API. Swap-in compatible (same `embed()`
  interface) — built to understand and explain what an embedding *is*.
- **Vector store**: ChromaDB when installed, pure-Python in-memory
  cosine-similarity fallback otherwise — same interface, graceful degradation.
- **Mock LLM**: `LLMClient(provider="mock")` returns deterministic answers
  calibrated to the Propgatics schema (real carrier names, real column names,
  real KPIs) — not random strings.

## Propgatics connection

This project is one half of a two-project portfolio:

- **Propgatics** (data layer) — generates and analyses the 100K shipment /
  25K incident dataset with Pandas, SQLite, Dash/Plotly dashboards.
- **This repo** (AI layer) — adds a 4-agent GenAI assistant on top of that
  data so non-technical users can query it in plain English.

The two share the same schema, the same carrier names, the same Canadian city
set, and the same KPIs — they are intentionally one end-to-end system.
