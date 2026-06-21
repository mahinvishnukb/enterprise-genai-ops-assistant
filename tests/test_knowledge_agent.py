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
