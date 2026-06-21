# Concepts cheat sheet

Everything here is also explained inline in the relevant file's docstring —
this is just the condensed version for last-minute review.

## GenAI / LLM basics
- **Token**: sub-word unit an LLM actually processes (~4 chars in English).
  Pricing and limits are measured in tokens.
- **Context window**: max tokens (prompt + completion) a model can attend
  to in one call. RAG exists largely because of this limit.
- **Prompt engineering**: structuring instructions/role/format so the model
  reliably outputs the shape you need (e.g. "respond with ONLY SQL" in
  `sql_agent.py`).
- **Function/tool calling**: model returns structured arguments for a
  predefined function instead of free text; your code executes the real
  function. This is what turns a chatbot into an "agent." See
  `router_agent.py` for the simplified version (classify -> dispatch).

## RAG (Retrieval-Augmented Generation)
- **Chunking** (`app/rag/chunking.py`): split long documents into
  overlapping windows so each embedding represents a focused, retrievable
  unit instead of one blurry average over a whole document.
- **Embedding** (`app/rag/embeddings.py`): text -> vector such that similar
  meaning -> small distance. This project uses a hashing-trick embedder
  (deterministic, offline) instead of a neural embedding model, specifically
  so CI/tests need no network call or API key — same `embed()` interface,
  swappable for OpenAI/sentence-transformers embeddings in production.
- **Vector search** (`app/rag/vector_store.py`): cosine similarity between
  the question's embedding and every stored chunk's embedding; return the
  top-k closest chunks.
- **Grounding**: the system prompt instructs the model to answer "ONLY
  using the provided context" — this is what makes RAG answers auditable
  and reduces hallucination vs. just asking the model from its training
  data.

## Agents
- **Multi-agent system**: instead of one monolithic prompt trying to do
  everything, separate agents each own one capability (RAG vs. NL2SQL), and
  a router decides which one handles a given request.
- **Agentic workflow**: an LLM call whose output controls subsequent
  program flow (which agent runs, which SQL executes), instead of just
  being displayed to a user.

## Backend
- **FastAPI / Pydantic**: Pydantic models define and validate the
  request/response shape; FastAPI uses them to auto-generate the
  interactive docs at `/docs` and to return 422 on bad input automatically.
- **Async Python**: `async def` endpoints let uvicorn serve many concurrent
  requests on one process without a thread blocked per slow I/O call (LLM
  API round-trip, DB query) — important once you swap the mock LLM for a
  real network call.
- **Dependency injection** (`app/api/deps.py`): FastAPI's `Depends()`
  builds agent singletons once and injects them into route handlers,
  instead of route handlers constructing their own dependencies (easier to
  swap implementations in tests).

## Database
- **ORM vs. raw SQL**: the app's own fixed read/write paths (saving a chat
  message) use the SQLAlchemy ORM for type safety; the SQL agent
  deliberately generates raw SQL because the question (and thus the query
  shape) isn't known ahead of time.
- **SQL injection defense-in-depth**: the SQL agent's regex gate
  (`sql_agent.py`) only allows single `SELECT` statements — never trust
  LLM output to be safe to execute directly.

## DevOps
- **Containerization (Docker)**: packages the app + its exact dependency
  versions into one portable unit so "works on my machine" stops being a
  problem. The frontend uses a multi-stage build (Node to compile, nginx
  to serve) to keep the final image small.
- **docker-compose**: defines multiple containers (db, backend, frontend)
  and the network between them — services find each other by service name
  (`db`, `backend`), not localhost/IP.
- **CI/CD** (`.github/workflows/ci.yml`): runs tests automatically on every
  push so a broken change can't silently merge. Using `LLM_PROVIDER=mock`
  here means CI needs zero secrets to go green.

## Testing
- **Mocking external dependencies**: tests inject `LLMClient(provider="mock")`
  instead of hitting a real LLM API — fast, free, deterministic, and tests
  the actual routing/parsing logic rather than a model's mood that day.
