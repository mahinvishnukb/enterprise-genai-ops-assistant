# Resume material — Projects section

Use this as a **Projects** entry (not a work-experience entry — be upfront
in the interview that this is a self-built project, not employment; that's
normal and expected for a portfolio piece, and it's much stronger to be
able to say "I built this to go deep on GenAI/agentic patterns" than to
imply it was a job).

---

**Enterprise GenAI Operations Assistant** — Personal Project | [GitHub link]
*Python, FastAPI, LangChain-style RAG, ChromaDB, PostgreSQL, SQLAlchemy, React, TypeScript, Docker, GitHub Actions CI*

- Built a multi-agent GenAI platform routing natural-language queries
  between a RAG-based document Q&A agent and a NL2SQL analytics agent,
  with an LLM-driven router agent for tool selection/dispatch.
- Implemented a full RAG pipeline (chunking, embedding, vector similarity
  search, grounded answer generation with cited sources) with a pluggable
  embedding/vector-store backend (ChromaDB in production, in-memory
  fallback for tests).
- Designed a NL2SQL agent with a regex-based safety gate restricting
  generated queries to read-only `SELECT` statements before execution
  against PostgreSQL — defense-in-depth against prompt-injection-driven
  destructive queries.
- Built a FastAPI backend (Pydantic schemas, async endpoints,
  dependency-injected agents) and a React/TypeScript chat frontend.
- Containerized the full stack (FastAPI + Postgres + React/nginx) with
  Docker Compose; wired a GitHub Actions CI pipeline running the pytest
  suite (mocked LLM calls, zero API keys required) on every push.
- Wrote unit tests covering chunking, embedding similarity ranking, SQL
  safety validation, agent routing logic, and API endpoints.

---

## Shorter one-liner (if space-constrained)

Built and tested a multi-agent GenAI platform (FastAPI + RAG + NL2SQL +
PostgreSQL + React, containerized with Docker, CI via GitHub Actions) that
routes natural-language queries between document Q&A and database
analytics agents.

## Likely interview questions you should be ready for

- "Walk me through what happens when a user asks a question." → trace
  RouterAgent.classify → dispatch → KnowledgeAgent or SQLAgent. (README
  diagram + the two agent files.)
- "How do you stop the SQL agent from running a destructive query?" →
  `app/agents/sql_agent.py`: regex gate requiring `SELECT`-only, rejecting
  `INSERT/UPDATE/DELETE/DROP/...`; plus pointing out a read-only DB role
  would be the production hardening on top of this.
- "What's RAG and why not just paste the whole document in the prompt?" →
  context window limits + cost; chunk -> embed -> retrieve top-k -> only
  the relevant chunks go in the prompt.
- "Why a mock LLM mode?" → deterministic, zero-cost, zero-network CI; same
  interface swaps to a real provider with one env var.
- "What would you add with more time?" → Analytics/Reporting agents,
  real embeddings (OpenAI or sentence-transformers), LangGraph-based
  multi-step planning instead of single-shot routing.
