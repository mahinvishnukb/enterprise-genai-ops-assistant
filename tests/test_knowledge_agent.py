from app.agents.knowledge_agent import KnowledgeAgent
from app.core.llm_client import LLMClient
from app.rag.vector_store import InMemoryVectorStore


def make_agent():
    return KnowledgeAgent(vector_store=InMemoryVectorStore(), llm=LLMClient(provider="mock"))


def test_answer_with_no_documents_says_so():
    agent = make_agent()
    result = agent.answer("what is the leave policy?")
    assert "no context" in result["answer"].lower() or "no documents" in result["answer"].lower()
    assert result["sources"] == []


def test_ingest_then_answer_returns_sources():
    agent = make_agent()
    chunk_count = agent.ingest("hr_policy", "Employees receive 20 days of paid leave annually.")
    assert chunk_count >= 1

    result = agent.answer("how many days of paid leave do employees get?")
    assert result["sources"]
    assert result["sources"][0]["doc_id"] == "hr_policy"


def test_ingest_is_idempotent_and_does_not_duplicate_chunks():
    agent = make_agent()
    agent.ingest("hr_policy", "Employees receive 20 days of paid leave annually.")
    agent.ingest("hr_policy", "Employees receive 20 days of paid leave annually.")

    assert len(agent.vector_store._chunks) == 1


def test_answer_refuses_when_ingested_docs_are_unrelated_to_the_question():
    agent = make_agent()
    agent.ingest("ops_report", "Shipment delays increased due to port congestion last quarter.")

    result = agent.answer("what is the capital of France?")
    assert result["sources"] == []
    assert "enough" in result["answer"].lower() or "no documents" in result["answer"].lower()
