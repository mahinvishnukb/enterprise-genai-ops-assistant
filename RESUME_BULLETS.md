# Resume material — Projects section

Use this as a **Projects** entry (not a work-experience entry — be upfront
in the interview that this is a self-built project, not employment; that's
normal and expected for a portfolio piece, and it's much stronger to say
"I built this to go deep on GenAI/agentic patterns" than to imply it was a job).

---

**Propgatics GenAI Operations Assistant** — Personal Project | [GitHub link]  
*Python · FastAPI · Multi-Agent RAG · BM25 Reranking · NL2SQL · SQLite · SQLAlchemy · React · TypeScript · Docker · GitHub Actions CI*

- Built a **4-agent GenAI platform** (RouterAgent → KnowledgeAgent, SQLAgent,
  AnalyticsAgent, ConversationAgent) on top of the Propgatics logistics dataset
  (100,000 shipments, 25,000 incidents, 5 carriers: UPS, FedEx, DHL, Canada Post,
  Purolator) — enabling plain-English queries over data that previously required
  writing SQL or navigating dashboards.
- Implemented **confidence-aware multi-agent routing**: the RouterAgent parses
  an LLM-generated confidence score and fans out to a secondary agent when
  confidence < 0.55, merging both answers for ambiguous queries (e.g. "which
  carrier is worst?" could be SQL or analytics).
- Built a **two-stage RAG pipeline**: wide vector recall → BM25-lite lexical
  reranking (blended vector + lexical scores) → relevance floor (MIN_RELEVANCE
  = 0.08) → grounded answer with cited source chunks. Idempotent ingest
  (delete-before-add) prevents ChromaDB chunk duplication on server restarts.
- Designed a **NL2SQL agent** with a regex safety gate restricting generated
  queries to read-only `SELECT` statements before execution against the full
  Propgatics schema (28-column `shipments` table + 19-column `incidents` table)
  — defense-in-depth against prompt-injection-driven destructive queries.
- Built an **AnalyticsAgent** using the code-first / LLM-as-narrator pattern:
  deterministic SQL computes KPIs (on-time rate, delay hotspots, carrier
  performance, weather impact, route risk scores), then the LLM synthesises
  a 3–5 sentence insight — auditability without sacrificing readability.
- Engineered a **mock LLM provider** (`LLMClient(provider="mock")`) that
  returns deterministic responses calibrated to the real Propgatics schema
  (carrier names, column values, KPIs) — CI runs the full pytest suite with
  zero API keys and zero network calls.
- Containerized the full stack (FastAPI + React/nginx) with Docker Compose;
  wired a **GitHub Actions CI pipeline** running pytest on every push.
- Built a **React/TypeScript chat frontend** with mobile support (iOS
  auto-zoom fix, `100dvh` viewport, tap-delay suppression), query history tab,
  stats panel, and per-message routing confidence indicator.

---

## Propgatics Logistics Intelligence Platform — Personal Project | [GitHub link]
*Python · Pandas · NumPy · SQLite · OpenRouteService API · Dash · Plotly · Jupyter*

- Generated a **100,000-row shipment dataset** and **25,000-row incident dataset**
  simulating real Canadian logistics operations across 5 carriers and 10 cities,
  with route distances computed via the OpenRouteService API against real city
  coordinates.
- Built interactive **Dash/Plotly analytics dashboards** covering on-time
  delivery KPIs (75.26% on-time rate, 2.52 h avg delay), carrier performance
  comparison, route risk scoring (0–100 composite, Low/Medium/High/Critical),
  and incident severity/financial-loss analysis.
- The dataset and schema (shipments + incidents tables) serve as the data layer
  for the GenAI Operations Assistant above — two projects, one end-to-end system.

---

## Shorter one-liner (if space-constrained)

Built a 4-agent GenAI platform (FastAPI + two-stage RAG + confidence-aware routing
+ NL2SQL + analytics narration + React, CI via GitHub Actions) on top of a
self-generated 100K-row logistics dataset (Propgatics) covering 5 carriers,
25K incidents, and real ORS-computed Canadian route data.

---

## Likely interview questions you should be ready for

- **"Walk me through what happens when a user asks a question."**  
  RouterAgent.classify → parses confidence → if high confidence, dispatch to primary agent (KnowledgeAgent / SQLAgent / AnalyticsAgent / ConversationAgent); if low confidence, fan out to secondary and merge answers.

- **"How does the RAG reranker work?"**  
  Two stages: (1) wide vector recall (top_k × CANDIDATE_MULTIPLIER candidates via cosine similarity); (2) BM25-lite rerank blending vector score and normalized lexical overlap (term frequency, IDF-weighted, stopwords removed). Chunks below MIN_RELEVANCE=0.08 are discarded with a refusal message rather than hallucinated answers.

- **"How do you stop the SQL agent from running a destructive query?"**  
  `app/agents/sql_agent.py`: regex gate requiring `SELECT`-only, rejecting `INSERT/UPDATE/DELETE/DROP/...`. In production you'd add a read-only DB role as a second layer.

- **"What's RAG and why not just paste the whole document in the prompt?"**  
  Context window limits + cost. Chunk → embed → retrieve top-k → only relevant chunks go in the prompt. The reranker adds a second quality gate so irrelevant chunks don't sneak through.

- **"Why does the AnalyticsAgent use SQL instead of asking the LLM to compute the numbers?"**  
  LLMs hallucinate arithmetic; SQL is deterministic and auditable. The LLM's job is narration ("here's what this means for the business"), not computation.

- **"What's the Propgatics connection?"**  
  Propgatics is the data/analytics layer (Pandas, SQLite, Dash). The GenAI assistant is the AI layer that makes that data queryable in plain English. Same schema, same KPIs, one end-to-end system.

- **"What would you add with more time?"**  
  Real embeddings (OpenAI or sentence-transformers), LangGraph-based multi-step planning instead of single-shot routing, streaming SSE responses to the frontend, PostgreSQL + pgvector in production.
