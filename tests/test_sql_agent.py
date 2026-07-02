import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.sql_agent import SQLAgent, UnsafeSQLError
from app.core.llm_client import LLMClient
from app.db.models import Base, Shipment


@pytest.fixture()
def sqlite_engine():
    """In-memory SQLite engine pre-seeded with two Propgatics-schema shipment rows."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    db.add(Shipment(
        shipment_id="SHP000001",
        carrier="UPS",
        origin="Toronto",
        destination="Vancouver",
        shipment_status="Delayed",
        delay_hours=4.5,
        on_time_delivery=0,
        risk_category="Medium",
        delivery_performance="Delayed",
        shipment_date=dt.date.today(),
    ))
    db.add(Shipment(
        shipment_id="SHP000002",
        carrier="FedEx",
        origin="Calgary",
        destination="Montreal",
        shipment_status="Delivered",
        delay_hours=0.0,
        on_time_delivery=1,
        risk_category="Low",
        delivery_performance="On Time",
        shipment_date=dt.date.today(),
    ))
    db.commit()
    db.close()
    return engine


def test_sql_agent_generates_and_executes_select(sqlite_engine):
    agent = SQLAgent(engine=sqlite_engine, llm=LLMClient(provider="mock"))
    result = agent.ask("Show delayed shipments last month")

    assert result["sql"].upper().startswith("SELECT")
    # Mock SQL queries shipments WHERE shipment_status IN ('Delayed',...)
    assert result["row_count"] == 1
    assert result["rows"][0]["shipment_status"] == "Delayed"


def test_sql_agent_rejects_unsafe_sql(sqlite_engine):
    agent = SQLAgent(engine=sqlite_engine, llm=LLMClient(provider="mock"))
    agent.generate_sql = lambda question: "DROP TABLE shipments;"

    with pytest.raises(UnsafeSQLError):
        agent.ask("drop everything")


def test_sql_agent_carrier_query_returns_rows(sqlite_engine):
    agent = SQLAgent(engine=sqlite_engine, llm=LLMClient(provider="mock"))
    result = agent.ask("Show all UPS shipments")

    assert result["sql"].upper().startswith("SELECT")
    # UPS row should be in results
    ups_rows = [r for r in result["rows"] if r.get("carrier") == "UPS"]
    assert len(ups_rows) >= 1


def test_sql_agent_validate_rejects_forbidden_keywords(sqlite_engine):
    agent = SQLAgent(engine=sqlite_engine, llm=LLMClient(provider="mock"))
    with pytest.raises(UnsafeSQLError):
        agent.validate_sql("SELECT * FROM shipments; DELETE FROM shipments")
