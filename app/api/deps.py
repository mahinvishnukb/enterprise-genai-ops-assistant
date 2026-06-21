"""
Singletons shared across requests, built once at process startup instead of
per-request. The vector store and agents hold in-memory state (ingested
chunks) that must persist across requests within the same process, so they
can't be constructed inside a request handler.
"""
from functools import lru_cache

from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.router_agent import RouterAgent
from app.agents.sql_agent import SQLAgent
from app.core.config import settings
from app.db.session import engine


@lru_cache
def get_knowledge_agent() -> KnowledgeAgent:
    return KnowledgeAgent()


@lru_cache
def get_sql_agent() -> SQLAgent:
    return SQLAgent(engine=engine)


@lru_cache
def get_router_agent() -> RouterAgent:
    return RouterAgent(knowledge_agent=get_knowledge_agent(), sql_agent=get_sql_agent())
