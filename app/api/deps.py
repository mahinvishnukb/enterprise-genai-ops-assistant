from functools import lru_cache

from app.agents.analytics_agent import AnalyticsAgent
from app.agents.conversation_agent import ConversationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.router_agent import RouterAgent
from app.agents.sql_agent import SQLAgent
from app.db.session import engine


@lru_cache
def get_knowledge_agent() -> KnowledgeAgent:
    return KnowledgeAgent()


@lru_cache
def get_sql_agent() -> SQLAgent:
    return SQLAgent(engine=engine)


@lru_cache
def get_analytics_agent() -> AnalyticsAgent:
    return AnalyticsAgent(engine=engine)


@lru_cache
def get_conversation_agent() -> ConversationAgent:
    return ConversationAgent()


@lru_cache
def get_router_agent() -> RouterAgent:
    return RouterAgent(
        knowledge_agent=get_knowledge_agent(),
        sql_agent=get_sql_agent(),
        analytics_agent=get_analytics_agent(),
        conversation_agent=get_conversation_agent(),
    )
