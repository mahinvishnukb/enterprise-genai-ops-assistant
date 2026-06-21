from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    agent: str
    answer: str | None = None
    sources: list[dict] | None = None
    sql: str | None = None
    rows: list[dict] | None = None
    row_count: int | None = None
    metrics: dict | None = None
    analysis_type: str | None = None


class SQLRequest(BaseModel):
    question: str = Field(..., min_length=1)


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int


class HealthResponse(BaseModel):
    status: str
    llm_provider: str


class StatsResponse(BaseModel):
    db_rows: int
    chunk_count: int
    queries_this_session: int
