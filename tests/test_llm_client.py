from app.core.llm_client import LLMClient


def test_mock_mode_sql_generation_for_delay_question():
    client = LLMClient(provider="mock")
    sql = client.chat(system="SQL_GENERATION blah", user="Show delayed shipments last month")
    assert sql.strip().upper().startswith("SELECT")
    assert "delayed" in sql.lower()


def test_mock_mode_router_routes_sql_keywords_to_sql_agent():
    client = LLMClient(provider="mock")
    route = client.chat(system="ROUTER blah", user="Show delayed shipments by count")
    assert route == "sql_agent"


def test_mock_mode_router_routes_policy_questions_to_knowledge_agent():
    client = LLMClient(provider="mock")
    route = client.chat(system="ROUTER blah", user="What is the leave policy?")
    assert route == "knowledge_agent"
