import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.sql_agent import SQLAgent, UnsafeSQLError
from app.core.llm_client import LLMClient
from app.db.models import Base, OperationsData


@pytest.fixture()
def sqlite_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    db.add(
        OperationsData(
            origin="Toronto", destination="Vancouver", status="delayed",
            delay_days=3, shipped_at=dt.date.today(),
        )
    )
    db.add(
        OperationsData(
            origin="Calgary", destination="Montreal", status="on_time",
            delay_days=0, shipped_at=dt.date.today(),
        )
    )
    db.commit()
    db.close()
    return engine


def test_sql_agent_generates_and_executes_select(sqlite_engine):
    agent = SQLAgent(engine=sqlite_engine, llm=LLMClient(provider="mock"))
    result = agent.ask("Show delayed shipments last month")

    assert result["sql"].upper().startswith("SELECT")
    assert result["row_count"] == 1
    assert result["rows"][0]["status"] == "delayed"


def test_sql_agent_rejects_unsafe_sql(sqlite_engine):
    agent = SQLAgent(engine=sqlite_engine, llm=LLMClient(provider="mock"))
    agent.generate_sql = lambda question: "DROP TABLE operations_data;"

    with pytest.raises(UnsafeSQLError):
        agent.ask("drop everything")
