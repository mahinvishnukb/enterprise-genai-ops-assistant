"""
Pydantic models = the request/response contract. FastAPI uses these for
three things at once: parsing incoming JSON into typed Python objects,
validating it (wrong type / missing field -> automatic 422 response, no
manual `if` checks), and generating the OpenAPI/Swagger schema at /docs.
That last part is why FastAPI auto-generates interactive API docs for free.
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User's natural-language question")


class ChatResponse(BaseModel):
    agent: str
    answer: str | None = None
    sources: list[dict] | None = None
    sql: str | None = None
    rows: list[dict] | None = None
    row_count: int | None = None


class SQLRequest(BaseModel):
    question: str = Field(..., min_length=1)


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
