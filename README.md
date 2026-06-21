# Enterprise GenAI Operations Assistant

A production-style AI platform that lets employees ask natural-language
questions over both unstructured documents (PDF/DOCX/PPT/CSV policies,
reports, SOPs) and structured operations data (a Postgres database),
through a single chat interface that automatically routes each question to
the right backend.

## Why this exists

Most internal company knowledge is split across two silos: documents
(policies, reports) that need semantic search, and databases (shipments,
tickets) that need precise queries. This project wires both into one
multi-agent system so a non-technical employee can ask either kind of
question without knowing which silo holds the answer.

## Architecture

```
                    ┌──────────────────┐
   POST /api/chat → │   RouterAgent    │  (classifies the question)
                    └──────┬───────────┘
                 ┌─────────┴─────────┐
                 ▼                   ▼
        ┌─────────────────┐  ┌──────────────┐
        │ KnowledgeAgent   │  │  SQLAgent    │
        │ (RAG)            │  │ (NL2SQL)     │
        └────────┬─────────┘  └──────┬───────┘
                 ▼                   ▼
        Vector store              PostgreSQL
        (Chroma / in-memory)      (operations_data)
```

* **RouterAgent** (`app/agents/router_agent.py`) — tool-calling/multi-agent
  orchestration. Classifies each question and dispatches it.
* **KnowledgeAgent** (`app/agents/knowledge_agent.py`) — RAG: chunk → embed
  → vector search → grounded answer with cited source chunks.
* **SQLAgent** (`app/agents/sql_agent.py`) — NL2SQL with a safety gate that
  rejects anything that isn't a single read-only `SELECT`.
* **LLMClient** (`app/core/llm_client.py`) — single seam for
  OpenAI/Anthropic, with a deterministic offline `mock` mode so tests and
  CI need zero API keys.
* **FastAPI** (`app/api/main.py`) — `/api/chat`, `/api/sql`, `/api/upload`,
  `/api/health`.
* **React + TypeScript** (`frontend/`) — single-page chat UI.
* **PostgreSQL** via SQLAlchemy (`app/db/`) — `users`, `documents`,
  `chat_history`, `operations_data` tables.

Every module's docstring explains the underlying concept (chunking,
embeddings, tokens/context window, tool calling, async, containerization,
CI/CD) — read those inline as you go, they're written as interview prep,
not just comments.

## Running it

**Fastest path (no Docker, no API key, no Postgres):**

```bash
pip install -r requirements.txt
cp .env.example .env                 # LLM_PROVIDER=mock by default
python -m app.db.seed                # seeds sample shipment data into SQLite
uvicorn app.api.main:app --reload
# in another terminal:
cd frontend && npm install && npm run dev
```

Open the frontend, upload `sample_docs/hr_leave_policy.txt`, then ask:
- "What is the leave policy?" → routes to KnowledgeAgent (RAG)
- "Show delayed shipments last month" → routes to SQLAgent (NL2SQL)

**Full stack with Docker + real Postgres:**

```bash
docker compose up --build
docker compose exec backend python -m app.db.seed
```

**Going live with a real model** (instead of the deterministic mock):
set `LLM_PROVIDER=openai` (or `anthropic`) and the matching API key in
`.env` — no code changes needed anywhere else, that's the point of
`LLMClient`.

## Tests

```bash
pytest -v
```

Tests use `LLM_PROVIDER=mock`, so they run with zero network calls and
zero API keys — the same way CI runs them (`.github/workflows/ci.yml`).

## What's deliberately scoped down (and why)

This was built to be deeply defensible in an interview rather than to tick
every box on a job description:

- **Embeddings**: a hand-rolled hashing-trick embedder (`app/rag/embeddings.py`)
  instead of calling OpenAI's embedding API or downloading a
  sentence-transformers model. It's swap-in compatible (same `embed()`
  interface) — the point was to *understand and be able to explain* what an
  embedding is, not to depend on a network call for a demo.
- **Vector store**: defaults to ChromaDB when installed, falls back to a
  pure-Python in-memory cosine-similarity store otherwise — same interface,
  graceful degradation.
- **Two agents deep (Knowledge + SQL), not five**: the JD lists Analytics,
  Reporting, and Multi-Agent as separate features. Here, the Router +
  Knowledge + SQL agents already demonstrate the multi-agent/tool-calling
  pattern end-to-end; a ReportingAgent or AnalyticsAgent would be a
  same-shaped addition (`app/agents/reporting_agent.py`, registered in the
  router) and is called out as a natural next step rather than padded in
  half-finished.

## Next steps if you have more time before the interview

1. Add `AnalyticsAgent` (pandas + plotly over `operations_data`) and
   `ReportingAgent` (templated executive summary), registered in
   `RouterAgent.agents`.
2. Swap `HashingEmbedder` for OpenAI embeddings once you have a key.
3. Add `LangGraph` for the router instead of a single classification call,
   if you want to demonstrate multi-step agent planning.
