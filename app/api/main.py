"""
FastAPI entrypoint — agents initialized once in on_startup and stored in
app.state, guaranteeing the same instance is used for startup ingestion
and every request handler.
"""
import tempfile
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.agents.analytics_agent import AnalyticsAgent
from app.agents.conversation_agent import ConversationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.router_agent import RouterAgent
from app.agents.sql_agent import SQLAgent, UnsafeSQLError
from app.api.deps import (
    get_analytics_agent,
    get_conversation_agent,
    get_knowledge_agent,
    get_router_agent,
    get_sql_agent,
)
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

app = FastAPI(
    title="Enterprise GenAI Operations Assistant",
    description="4-agent RAG + NL2SQL platform",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # wildcard kept for Vercel preview URLs
    allow_methods=["*"],
    allow_headers=["*"],
)

_query_lock = threading.Lock()
_query_counter = 0


@app.on_event("startup")
def on_startup():
    # 1. DB tables + seed
    Base.metadata.create_all(engine)
    from app.db.seed import seed
    seed()

    # 2. Build agent singletons and store on app.state
    ka = KnowledgeAgent()
    sa = SQLAgent(engine=engine)
    aa = AnalyticsAgent(engine=engine)
    ca = ConversationAgent()
    ra = RouterAgent(knowledge_agent=ka, sql_agent=sa, analytics_agent=aa, conversation_agent=ca)

    app.state.knowledge_agent = ka
    app.state.sql_agent = sa
    app.state.analytics_agent = aa
    app.state.conversation_agent = ca
    app.state.router_agent = ra

    # 3. Auto-ingest sample docs into the knowledge agent
    _auto_ingest(ka)


def _auto_ingest(ka: KnowledgeAgent):
    # Try disk first (local dev), then fall back to embedded strings (Render/prod)
    sample_dir = Path(__file__).resolve().parent.parent.parent / "sample_docs"
    loaded = 0
    if sample_dir.exists():
        for p in sorted(sample_dir.glob("*.txt")):
            if p.name.startswith("._"):
                continue
            try:
                ka.ingest(p.stem, p.read_text(encoding="utf-8"))
                print(f"[startup] ingested {p.name}")
                loaded += 1
            except Exception as e:
                print(f"[startup] failed {p.name}: {e}")
    if loaded == 0:
        for doc_id, text in _EMBEDDED_DOCS.items():
            try:
                ka.ingest(doc_id, text)
                print(f"[startup] ingested embedded:{doc_id}")
            except Exception as e:
                print(f"[startup] failed embedded:{doc_id}: {e}")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", llm_provider=settings.llm_provider)


@app.get("/api/stats", response_model=StatsResponse)
async def stats(knowledge_agent: KnowledgeAgent = Depends(get_knowledge_agent)):
    db = SessionLocal()
    try:
        row_count = db.execute(text("SELECT COUNT(*) FROM shipments")).scalar() or 0
    except Exception:
        try:
            row_count = db.execute(text("SELECT COUNT(*) FROM operations_data")).scalar() or 0
        except Exception:
            row_count = 0
    finally:
        db.close()
    chunk_count = len(getattr(knowledge_agent.vector_store, "_chunks", []))
    return StatsResponse(db_rows=int(row_count), chunk_count=chunk_count, queries_this_session=_query_counter)


@app.get("/api/documents", response_model=list[DocumentInfo])
async def list_documents(knowledge_agent: KnowledgeAgent = Depends(get_knowledge_agent)):
    chunks = getattr(knowledge_agent.vector_store, "_chunks", [])
    counts: dict[str, int] = {}
    for chunk in chunks:
        counts[chunk.doc_id] = counts.get(chunk.doc_id, 0) + 1
    builtin = set(_EMBEDDED_DOCS.keys()) | {
        "propgatics_overview", "propgatics_kpi_summary", "propgatics_carrier_performance",
        "hr_leave_policy", "q1_operations_report",
    }
    return [
        DocumentInfo(doc_id=doc_id, chunk_count=count, source="builtin" if doc_id in builtin else "uploaded")
        for doc_id, count in counts.items()
    ]


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, router: RouterAgent = Depends(get_router_agent)):
    global _query_counter
    with _query_lock:
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


# ─── Embedded sample docs ─────────────────────────────────────────────────────

_EMBEDDED_DOCS = {
    "hr_leave_policy": """Enterprise Operations Inc. HR Leave Policy (Effective January 2026)

ANNUAL LEAVE: All full-time employees accrue 20 days of paid annual leave per calendar year, credited quarterly (5 days/quarter). Unused leave up to 5 days may carry over; remainder forfeited December 31st. Leave cannot be taken in first 90 days of employment.

SICK LEAVE: Employees receive 10 paid sick days per year, no carryover. Medical certificate required for sick leave exceeding 3 consecutive days. Exhausted sick leave may be followed by up to 30 days unpaid medical leave with HR approval.

PARENTAL LEAVE: Primary caregivers receive 16 weeks paid parental leave. Secondary caregivers receive 4 weeks. Must commence within 12 months of birth or adoption.

BEREAVEMENT LEAVE: 5 paid days for immediate family (spouse, child, parent, sibling). 2 paid days for extended family.

REMOTE WORK: Up to 3 days/week with manager approval. Full remote requires VP approval, reviewed quarterly. Core hours: 10am-3pm local time.

PERFORMANCE REVIEWS: Bi-annually in June and December. Compensation tied to year-end review. 2 weeks notice before review.

LEAVE REQUEST PROCEDURE: Submit via HR portal at least 5 business days in advance. Q4 peak (Oct-Dec) requires 10 business days. Emergency leave: notify manager immediately, formal docs within 48 hours.

ONBOARDING: HR intake forms within 3 business days. Payroll setup within 2 weeks. Compliance training within 30 days. Health insurance registration within 14 days.""",

    "propgatics_overview": """Propgatics Logistics Intelligence Platform — Platform Overview

ABOUT PROPGATICS
Propgatics is an end-to-end logistics and shipment analytics platform simulating a real-world operational intelligence system for logistics, transportation, and supply chain environments. The platform covers shipment lifecycle tracking, delay analysis, operational KPIs, route intelligence, carrier performance, and incident monitoring.

DATASET SCALE: 100,000 shipment records; 25,000 incident records. Carriers: UPS, FedEx, DHL, Canada Post, Purolator. Cities: Toronto, Vancouver, Calgary, Montreal, Edmonton, Halifax, Moncton, Kelowna, Ottawa, Winnipeg.

DATA GENERATION: Route data (distance_km, estimated_duration_hours) generated via OpenRouteService (ORS) API. All other fields synthesised with controlled randomisation calibrated to realistic logistics distributions.

SHIPMENT STATUS: Delivered, Minor Delay, Delayed, Critical Delay. RISK SCORES: 0–100 composite score. Categories: Low (<20), Medium (20–40), High (40–60), Critical (>60). Mean: 16.32.""",

    "propgatics_kpi_summary": """Propgatics Platform KPI Summary (Full Dataset: 100,000 Shipments)

On-time delivery rate: 75.26%. Delayed rate: 24.74%. Average delay: 2.52 hours. Total shipping revenue: CAD $7,430,259. Total delivery cost: CAD $18,860,452. Average route risk score: 16.32/100. Total incidents: 25,000.

CARRIER PERFORMANCE: Canada Post 75.59% on-time (avg delay 2.50h, avg cost $74.43). UPS 75.59% (2.50h, $74.26). DHL 75.44% (2.44h, $74.37). Purolator 75.22% (2.56h, $74.32). FedEx 74.96% (2.59h, $74.06).

KEY FINDINGS: On-time rate below 85% industry benchmark. Narrow carrier spread (0.63pp) confirms systemic issues. Delivery cost ($188.60/shipment) exceeds revenue ($74.30/shipment) by 2.5x. Incident rate 25% (1 per 4 shipments). Recommend SLA renegotiation, weather-aware routing, pricing review.""",

    "propgatics_carrier_performance": """Propgatics Carrier Performance & Incident Report

INCIDENT TYPES (25,000 total): Failed Delivery Attempt 28%, Damaged Shipment 22%, Customs Hold 18%, Weather Delay 15%, Lost Package 10%, Mechanical Failure 5%, Address Error 2%.

SEVERITY: Low 41% (avg loss $800, 36h resolution), Medium 34% ($1,500, 60h), High 15% ($2,200, 84h), Critical 10% ($2,800, 96h). Status: Resolved 65%, Under Investigation 25%, Open 10%.

TOP ROUTES: Calgary–Edmonton (busiest, 300km, best on-time). Toronto–Vancouver and Toronto–Montreal (highest revenue). Vancouver-bound long-haul routes (highest delay rate, mountain pass weather exposure).""",

    "q1_operations_report": """Enterprise Operations Inc. Q1 2026 Operations Report

EXECUTIVE SUMMARY: Shipment volume grew 12% QoQ to 1,847 total. On-time delivery: 86% (target 90%). Revenue $4.2M (+9% QoQ). Gross margin 33%, down from 36% due to carrier surcharges.

SHIPMENT METRICS: Total 1,847. On-time 1,588 (86%). Delayed 203 (11%). Cancelled 56 (3%). Average delay 3.8 days.

TOP ROUTES (on-time rate): New York to Montreal 94%, Toronto to Calgary 92%, Seattle to Toronto 91%.
WORST ROUTES (delay rate): Chicago to Vancouver 31%, Seattle to Montreal 24%, Calgary to New York 19%.

VANCOUVER PORT CONGESTION: Added 2.3 days average delay to westbound shipments Feb-Mar. Cause: labour disputes and increased Asian imports. Mitigation: rerouting through Seattle. Resolution expected Q2 2026.

CARRIER PERFORMANCE: FastFreight Inc (primary): 88% SLA compliance. NorthRoute Logistics (secondary): 79% SLA - underperforming, contract review April. PacificLink (new, Feb 2026): 85% on Vancouver routes.

CANCELLATIONS: 3% rate (56 shipments). Causes: customer holds 42%, carrier capacity 35%, customs 23%.

FINANCIALS: Revenue $4.2M. Carrier costs $2.8M (+13%). Gross margin 33%. Delay penalties $84,000.

Q2 ACTION ITEMS: Renegotiate Vancouver port SLA by April 30. Pilot secondary carrier Calgary-Montreal. Real-time delay alerts for 2+ day delays. Review NorthRoute contract. Target 90% on-time by Q2 end.""",
}
