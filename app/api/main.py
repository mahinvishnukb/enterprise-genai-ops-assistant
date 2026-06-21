"""
FastAPI entrypoint. Run with: uvicorn app.api.main:app --reload

ASYNC NOTE: endpoints below are declared `async def`. FastAPI runs sync
def endpoints in a thread pool automatically, so async isn't *required*
here since our agent calls are CPU-bound/sync — but in production, the LLM
calls and DB queries this code makes are I/O-bound (network round trips).
Declaring endpoints async and using an async HTTP client/DB driver lets
uvicorn serve hundreds of concurrent requests on one process instead of
blocking a worker thread per slow LLM call. Kept async here so swapping in
`AsyncOpenAI` / `asyncpg` later doesn't require touching the route
signatures.
"""
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.router_agent import RouterAgent
from app.agents.sql_agent import SQLAgent, UnsafeSQLError
from app.api.deps import get_knowledge_agent, get_router_agent, get_sql_agent
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    DocumentInfo,
    HealthResponse,
    SQLRequest,
    StatsResponse,
    UploadResponse,
)
from app.core.config import settings
from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.rag.loaders import extract_text

_query_counter = 0

app = FastAPI(
    title="Enterprise GenAI Operations Assistant",
    description="RAG knowledge chat + NL2SQL analytics over enterprise docs and operations data.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend's origin in real prod
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(engine)
    from app.db.seed import seed
    seed()
    _auto_ingest_sample_docs()


def _auto_ingest_sample_docs():
    """Ingest built-in sample docs so the Knowledge Agent works out of the box."""
    from pathlib import Path
    ka = get_knowledge_agent()

    # Try reading from disk first (dev), fall back to embedded strings (prod)
    sample_dir = Path(__file__).resolve().parent.parent.parent / "sample_docs"
    docs_loaded = 0
    if sample_dir.exists():
        for doc_path in sorted(sample_dir.glob("*.txt")):
            if doc_path.name.startswith("._"):
                continue
            try:
                text = doc_path.read_text(encoding="utf-8")
                ka.ingest(doc_path.stem, text)
                print(f"Auto-ingested from disk: {doc_path.name}")
                docs_loaded += 1
            except Exception as e:
                print(f"Failed to ingest {doc_path.name}: {e}")

    if docs_loaded == 0:
        # Embedded fallback — always works in any environment
        for doc_id, text in _EMBEDDED_DOCS.items():
            try:
                ka.ingest(doc_id, text)
                print(f"Auto-ingested embedded: {doc_id}")
            except Exception as e:
                print(f"Failed to ingest embedded {doc_id}: {e}")


_EMBEDDED_DOCS = {
    "hr_leave_policy": """Enterprise Operations Inc. — HR Leave Policy (Effective January 2026)

ANNUAL LEAVE: All full-time employees accrue 20 days of paid annual leave per calendar year, credited at the start of each quarter. Unused leave up to 5 days may be carried over; the remainder is forfeited on December 31st. Leave cannot be taken in the first 90 days of employment.

SICK LEAVE: Employees receive 10 paid sick days per year with no carryover. A medical certificate is required for sick leave longer than 3 consecutive days. If exhausted, employees may apply for unpaid medical leave of up to 30 days with HR approval.

PARENTAL LEAVE: Primary caregivers receive 16 weeks of paid parental leave. Secondary caregivers receive 4 weeks. Leave must commence within 12 months of birth or adoption.

BEREAVEMENT LEAVE: 5 paid days for immediate family (spouse, child, parent, sibling). 2 paid days for extended family.

REMOTE WORK: Up to 3 days per week with manager approval. Full remote requires VP approval, reviewed quarterly. Core hours: 10am–3pm local time.

PERFORMANCE REVIEWS: Bi-annually in June and December. Compensation adjustments tied to year-end review. 2 weeks notice before scheduled review.

LEAVE REQUEST PROCEDURE: Submit through HR portal at least 5 business days in advance. During Q4 peak (October–December), 10 business days required. Emergency leave: report to manager immediately, formal docs within 48 hours.

ONBOARDING: Complete HR intake forms within 3 business days. Set up payroll within 2 weeks. Complete compliance training within 30 days. Register for health insurance within 14 days.""",

    "q1_operations_report": """Enterprise Operations Inc. — Q1 2026 Operations Report

EXECUTIVE SUMMARY: Shipment volume grew 12% QoQ to 1,847 total shipments. On-time delivery rate: 86% (target: 90%). Revenue up 9% to $4.2M. Gross margin 33%, down from 36% in Q4 due to carrier surcharges.

SHIPMENT PERFORMANCE: Total: 1,847. On-time: 1,588 (86%). Delayed: 203 (11%). Cancelled: 56 (3%). Average delay: 3.8 days.

TOP ROUTES (on-time): New York→Montreal 94%, Toronto→Calgary 92%, Seattle→Toronto 91%.
UNDERPERFORMING ROUTES: Chicago→Vancouver 31% delay rate, Seattle→Montreal 24%, Calgary→New York 19%.

VANCOUVER PORT CONGESTION: Added 2.3 days average delay to westbound shipments in Feb–Mar. Caused by labour disputes and increased Asian imports. Mitigation: rerouting through Seattle. Resolution expected Q2 2026.

CARRIER PERFORMANCE: FastFreight Inc. (primary): 88% SLA compliance. NorthRoute Logistics (secondary): 79% — underperforming, contract review April. PacificLink (new, Feb 2026): 85% on Vancouver routes.

CANCELLATIONS: 3% rate (56 shipments). Causes: customer holds 42%, carrier capacity 35%, customs 23%.

FINANCIALS: Revenue $4.2M (+9% QoQ). Carrier costs $2.8M (+13%). Gross margin 33%. Delay penalties: $84,000.

Q2 ACTION ITEMS: 1) Renegotiate Vancouver port SLA by April 30. 2) Pilot secondary carrier on Calgary–Montreal. 3) Implement real-time delay alerts for >2 day threshold. 4) Review NorthRoute contract. 5) Target 90% on-time rate by end of Q2.""",
}


@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", llm_provider=settings.llm_provider)


@app.get("/api/stats", response_model=StatsResponse)
async def stats(knowledge_agent: KnowledgeAgent = Depends(get_knowledge_agent)):
    db = SessionLocal()
    try:
        row = db.execute(text("SELECT COUNT(*) FROM operations_data")).scalar() or 0
    except Exception:
        row = 0
    finally:
        db.close()
    chunk_count = len(getattr(knowledge_agent.vector_store, "_chunks", []))
    return StatsResponse(db_rows=int(row), chunk_count=chunk_count, queries_this_session=_query_counter)


@app.get("/api/documents", response_model=list[DocumentInfo])
async def list_documents(knowledge_agent: KnowledgeAgent = Depends(get_knowledge_agent)):
    chunks = getattr(knowledge_agent.vector_store, "_chunks", [])
    counts: dict[str, int] = {}
    for chunk in chunks:
        counts[chunk.doc_id] = counts.get(chunk.doc_id, 0) + 1
    builtin = set(_EMBEDDED_DOCS.keys())
    return [
        DocumentInfo(doc_id=doc_id, chunk_count=count, source="builtin" if doc_id in builtin else "uploaded")
        for doc_id, count in counts.items()
    ]


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, router: RouterAgent = Depends(get_router_agent)):
    global _query_counter
    _query_counter += 1
    result = router.handle(req.message, history=req.history)
    return ChatResponse(**result)


@app.post("/api/sql", response_model=ChatResponse)
async def sql_query(req: SQLRequest, sql_agent: SQLAgent = Depends(get_sql_agent)):
    try:
        result = sql_agent.ask(req.question)
    except UnsafeSQLError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChatResponse(agent="sql_agent", **result)


@app.post("/api/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    knowledge_agent: KnowledgeAgent = Depends(get_knowledge_agent),
):
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        text = extract_text(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    doc_id = Path(file.filename).stem
    chunk_count = knowledge_agent.ingest(doc_id, text)
    return UploadResponse(doc_id=doc_id, filename=file.filename, chunk_count=chunk_count)
