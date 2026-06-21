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
    chunk_count = len(knowledge_agent.vector_store._store) if hasattr(knowledge_agent.vector_store, "_store") else 0
    return StatsResponse(db_rows=int(row), chunk_count=chunk_count, queries_this_session=_query_counter)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, router: RouterAgent = Depends(get_router_agent)):
    global _query_counter
    _query_counter += 1
    result = router.handle(req.message)
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
