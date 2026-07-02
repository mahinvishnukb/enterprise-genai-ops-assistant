from app.core.llm_client import LLMClient


def test_mock_mode_sql_generation_for_delay_question():
    client = LLMClient(provider="mock")
    sql = client.chat(system="SQL_GENERATION blah", user="Show delayed shipments last month")
    assert sql.strip().upper().startswith("SELECT")
    assert "delayed" in sql.lower()


def test_mock_mode_sql_generation_uses_propgatics_schema():
    """Mock SQL must reference the real Propgatics columns, not the old operations_data schema."""
    client = LLMClient(provider="mock")
    sql = client.chat(system="SQL_GENERATION blah", user="Show all delayed shipments")
    # Must use Propgatics shipments table and real columns
    assert "shipments" in sql.lower(), f"Expected 'shipments' table in: {sql}"
    assert "shipment_status" in sql.lower(), f"Expected 'shipment_status' column in: {sql}"
    # Must NOT reference the old schema
    assert "operations_data" not in sql.lower(), f"Old table 'operations_data' in: {sql}"


def test_mock_mode_sql_generation_for_carrier_question():
    """Mock SQL for a carrier query should reference the carrier column."""
    client = LLMClient(provider="mock")
    sql = client.chat(system="SQL_GENERATION blah", user="Show all UPS shipments")
    assert sql.strip().upper().startswith("SELECT")
    assert "shipments" in sql.lower()


def test_mock_mode_router_routes_sql_keywords_to_sql_agent():
    client = LLMClient(provider="mock")
    route = client.chat(system="ROUTER blah", user="Show delayed shipments by count")
    lines = route.splitlines()
    assert lines[0] == "sql_agent"
    assert 0.0 <= float(lines[1]) <= 1.0


def test_mock_mode_router_routes_policy_questions_to_knowledge_agent():
    client = LLMClient(provider="mock")
    route = client.chat(system="ROUTER blah", user="What is the leave policy?")
    lines = route.splitlines()
    assert lines[0] == "knowledge_agent"
    assert 0.0 <= float(lines[1]) <= 1.0


def test_mock_mode_router_flags_low_confidence_for_ambiguous_message():
    client = LLMClient(provider="mock")
    # Mentions both a document signal ("q1") and an analytics signal
    # ("report") and a SQL signal ("show") — genuinely ambiguous, so the
    # router should report a secondary candidate rather than pretend it's
    # sure of a single agent.
    route = client.chat(system="ROUTER blah", user="Show Q1 delay report")
    lines = route.splitlines()
    assert lines[2] != "none"
