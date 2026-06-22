from app.agents.analytics_agent import AnalyticsAgent
from app.agents.conversation_agent import ConversationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.router_agent import RouteDecision, RouterAgent
from app.agents.sql_agent import SQLAgent
from app.core.llm_client import LLMClient
from app.db.models import Base
from app.db.session import engine
from app.rag.vector_store import InMemoryVectorStore


def make_router():
    Base.metadata.create_all(engine)
    knowledge_agent = KnowledgeAgent(vector_store=InMemoryVectorStore(), llm=LLMClient(provider="mock"))
    knowledge_agent.ingest("hr_policy", "Employees get 20 days of paid leave annually under company policy.")
    sql_agent = SQLAgent(engine=engine, llm=LLMClient(provider="mock"))
    analytics_agent = AnalyticsAgent(engine=engine, llm=LLMClient(provider="mock"))
    conversation_agent = ConversationAgent(llm=LLMClient(provider="mock"))
    return RouterAgent(
        knowledge_agent=knowledge_agent,
        sql_agent=sql_agent,
        analytics_agent=analytics_agent,
        conversation_agent=conversation_agent,
        llm=LLMClient(provider="mock"),
    )


def test_router_dispatches_policy_question_to_knowledge_agent():
    router = make_router()
    result = router.handle("What is the leave policy?")
    assert result["agent"] == "knowledge_agent"
    assert "answer" in result


def test_router_dispatches_shipment_question_to_sql_agent():
    router = make_router()
    result = router.handle("Show delayed shipments last month")
    assert result["agent"] == "sql_agent"
    assert "sql" in result


def test_router_dispatches_insight_question_to_analytics_agent():
    router = make_router()
    result = router.handle("Give me a KPI summary of operations")
    assert result["agent"] == "analytics_agent"


def test_router_dispatches_greeting_to_conversation_agent():
    router = make_router()
    result = router.handle("Hello there")
    assert result["agent"] == "conversation_agent"


def test_router_handle_never_crashes_on_garbage_classification():
    router = make_router()
    # classify() is a documented override point — handle() must survive even
    # a caller that monkeypatches it to return something malformed.
    router.classify = lambda question: "some_unregistered_tool"
    result = router.handle("anything")
    assert result["agent"] == "conversation_agent"


def test_router_high_confidence_does_not_fan_out():
    router = make_router()
    router.classify = lambda question: RouteDecision(primary="knowledge_agent", confidence=0.95, secondary="sql_agent")
    result = router.handle("What is the leave policy?")
    assert result["agent"] == "knowledge_agent"
    assert result["routing"]["ambiguous"] is False
    assert "also_considered" not in result["routing"]


def test_router_flags_ambiguous_classification_and_considers_secondary():
    router = make_router()
    router.classify = lambda question: RouteDecision(primary="sql_agent", confidence=0.4, secondary="analytics_agent")
    result = router.handle("Show me the route performance")
    assert result["agent"] == "sql_agent"
    assert result["routing"]["ambiguous"] is True
    assert result["routing"]["also_considered"] == "analytics_agent"
    assert "secondary_answer" in result["routing"]
