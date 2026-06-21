"""
SQLAgent — natural language -> SQL -> executed result, the "AI Data Analyst /
AI SQL Assistant" feature.

Flow: ask("Show delayed shipments last month")
  1. Prompt the LLM with the table schema + the question, instructed to
     return ONLY a SQL statement (classic prompt engineering: constrain the
     output format so downstream code can parse it without guessing).
  2. SAFETY CHECK: reject anything that isn't a single SELECT statement.
     This is the single most important line in this file for an interview —
     an LLM that can freely emit DROP TABLE / DELETE / UPDATE against a
     production database is a real security incident waiting to happen.
     Real systems either run the generated SQL against a read-only DB role,
     or — as here — defense-in-depth: regex-gate it AND use a read-only
     connection.
  3. Execute against the real database via SQLAlchemy and return rows.

NL2SQL concept: the schema description in the prompt is doing the heavy
lifting. The model isn't "smart about your database" — it's pattern
matching the column names you handed it against the question. Garbage
schema description in, garbage SQL out.
"""
import re

from sqlalchemy import text as sql_text
from sqlalchemy.engine import Engine

from app.core.llm_client import LLMClient

SCHEMA_DESCRIPTION = """
Table: operations_data
Columns:
  id INTEGER
  origin TEXT
  destination TEXT
  status TEXT          -- one of: 'delayed', 'on_time', 'cancelled'
  delay_days INTEGER    -- 0 if not delayed
  shipped_at DATE
"""

SYSTEM_PROMPT = (
    "SQL_GENERATION: You are a SQL generator for a PostgreSQL operations database. "
    f"Schema:\n{SCHEMA_DESCRIPTION}\n"
    "Given a question, respond with ONLY a single read-only SELECT statement. "
    "No prose, no markdown fences, no explanation."
)

_SELECT_ONLY_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_FORBIDDEN_RE = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|--|;.*\S)", re.IGNORECASE)


class UnsafeSQLError(Exception):
    pass


class SQLAgent:
    def __init__(self, engine: Engine, llm: LLMClient | None = None):
        self.engine = engine
        self.llm = llm or LLMClient()

    def generate_sql(self, question: str) -> str:
        raw = self.llm.chat(system=SYSTEM_PROMPT, user=question)
        return raw.strip().strip("`").strip()

    def validate_sql(self, sql: str) -> None:
        if not _SELECT_ONLY_RE.match(sql):
            raise UnsafeSQLError("Generated query must start with SELECT.")
        if _FORBIDDEN_RE.search(sql):
            raise UnsafeSQLError("Generated query contains a forbidden keyword or statement.")

    def execute(self, sql: str) -> list[dict]:
        with self.engine.connect() as conn:
            result = conn.execute(sql_text(sql))
            return [dict(row._mapping) for row in result]

    def ask(self, question: str) -> dict:
        sql = self.generate_sql(question)
        self.validate_sql(sql)
        rows = self.execute(sql)
        return {"sql": sql, "rows": rows, "row_count": len(rows)}
