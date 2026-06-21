from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.router_agent import RouterAgent
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
    return RouterAgent(knowledge_agent, sql_agent, llm=LLMClient(provider="mock"))


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


def test_router_falls_back_to_knowledge_agent_on_unknown_label():
    router = make_router()
    router.llm = LLMClient(provider="mock")
    router.classify = lambda question: "some_unregistered_tool"
    # handle() should never crash even if classify somehow returns garbage,
    # because dispatch only checks for "sql_agent" and defaults otherwise.
    result = router.handle("anything")
    assert result["agent"] == "knowledge_agent"
