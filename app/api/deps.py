"""
Agent dependencies — using FastAPI app.state instead of lru_cache.
This guarantees the SAME instance is used across startup ingestion and
all request handlers in the same process.
"""
from fastapi import Request

from app.agents.analytics_agent import AnalyticsAgent
from app.agents.conversation_agent import ConversationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.router_agent import RouterAgent
from app.agents.sql_agent import SQLAgent


def get_knowledge_agent(request: Request) -> KnowledgeAgent:
    return request.app.state.knowledge_agent


def get_sql_agent(request: Request) -> SQLAgent:
    return request.app.state.sql_agent


def get_analytics_agent(request: Request) -> AnalyticsAgent:
    return request.app.state.analytics_agent


def get_conversation_agent(request: Request) -> ConversationAgent:
    return request.app.state.conversation_agent


def get_router_agent(request: Request) -> RouterAgent:
    return request.app.state.router_agent
