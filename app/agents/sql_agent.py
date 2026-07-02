"""
SQLAgent — natural language -> SQL -> executed result.

Flow: ask("Show delayed shipments from Calgary last month")
  1. Prompt the LLM with the full table schema + question, instructed to
     return ONLY a SQL SELECT statement (classic output-format constraint).
  2. SAFETY CHECK: reject anything that is not a single SELECT statement.
     This is the most important line in this file — an LLM that can freely
     emit DROP TABLE / DELETE / UPDATE against a production database is a
     real security incident waiting to happen.  Defense-in-depth: regex
     gate + read-only connection scope.
  3. Execute against SQLite via SQLAlchemy and return rows.

NL2SQL concept: the schema description in the prompt does the heavy lifting.
The model is pattern-matching column names against the question — garbage
schema description in, garbage SQL out.

Tables (Propgatics Logistics Intelligence Platform):
  shipments  — 5 000 seeded rows (full dataset: 100K), one row per shipment
  incidents  — 1 000 seeded rows (full dataset: 25K), one row per incident
"""
import re

from sqlalchemy import text as sql_text
from sqlalchemy.engine import Engine

from app.core.llm_client import LLMClient

SCHEMA_DESCRIPTION = """
Table: shipments
  Columns:
    id                      INTEGER  -- auto-increment primary key
    shipment_id             TEXT     -- e.g. 'SHP000001'
    tracking_number         TEXT     -- e.g. 'TRK5537253172'
    carrier                 TEXT     -- 'UPS', 'FedEx', 'DHL', 'Canada Post', 'Purolator'
    origin                  TEXT     -- Canadian city: 'Toronto','Vancouver','Calgary','Montreal',
                                     --   'Edmonton','Halifax','Moncton','Kelowna','Ottawa', etc.
    destination             TEXT     -- same city set as origin
    distance_km             REAL
    estimated_duration_hours REAL
    shipment_date           DATE     -- ISO format YYYY-MM-DD
    estimated_delivery_date DATE
    actual_delivery_date    DATE
    shipment_status         TEXT     -- 'Delivered', 'Delayed', 'Minor Delay', 'Critical Delay'
    delay_hours             REAL     -- 0.0 if on time
    package_weight_kg       REAL
    package_type            TEXT     -- 'Small Parcel','Large Parcel','Pallet','Envelope'
    shipping_cost_cad       REAL
    priority_level          TEXT     -- 'Standard','Express','Same-Day'
    service_level           TEXT     -- 'Economy','Two-Day','Priority','Overnight'
    customer_type           TEXT     -- 'Business','Individual'
    weather_condition       TEXT     -- 'Clear','Rain','Snow','Fog','Cloudy','Storm'
    traffic_level           TEXT     -- 'Low','Medium','High'
    warehouse_id            TEXT     -- e.g. 'WH-TOR-001'
    driver_id               TEXT     -- e.g. 'DRV00644'
    fuel_cost_cad           REAL
    delivery_cost_cad       REAL
    delay_reason            TEXT     -- 'None','Weather','Traffic','Mechanical','Customs','Strike'
    on_time_delivery        INTEGER  -- 1 = on time, 0 = late
    route_risk_score        REAL     -- 0-100 composite risk score
    risk_category           TEXT     -- 'Low','Medium','High','Critical'
    delivery_performance    TEXT     -- 'On Time','Delayed'

Table: incidents
  Columns:
    id                          INTEGER
    incident_id                 TEXT     -- e.g. 'INC000001'
    shipment_id                 TEXT     -- references shipments.shipment_id
    tracking_number             TEXT
    carrier                     TEXT
    origin                      TEXT
    destination                 TEXT
    incident_type               TEXT     -- 'Damaged Shipment','Failed Delivery Attempt',
                                         --   'Lost Package','Customs Hold','Weather Delay',
                                         --   'Mechanical Failure','Address Error'
    severity_level              TEXT     -- 'Low','Medium','High','Critical'
    incident_status             TEXT     -- 'Resolved','Under Investigation','Open'
    incident_date               TEXT     -- ISO datetime string
    delay_hours                 REAL
    weather_condition           TEXT
    traffic_level               TEXT
    route_risk_score            REAL
    estimated_financial_loss_cad REAL
    resolution_action           TEXT
    resolution_time_hours       REAL
    warehouse_id                TEXT
    driver_id                   TEXT

Useful query patterns:
  -- Delayed shipments:   WHERE shipment_status IN ('Delayed','Minor Delay','Critical Delay')
  -- On-time shipments:   WHERE on_time_delivery = 1
  -- By carrier:          WHERE carrier = 'FedEx'
  -- By date range:       WHERE shipment_date BETWEEN '2026-01-01' AND '2026-03-31'
  -- High-risk:           WHERE risk_category IN ('High','Critical')
  -- Critical incidents:  incidents WHERE severity_level = 'Critical'
"""

SYSTEM_PROMPT = (
    "SQL_GENERATION: You are a SQL generator for a SQLite logistics database. "
    f"Schema:\n{SCHEMA_DESCRIPTION}\n"
    "Given a question, respond with ONLY a single read-only SELECT statement. "
    "No prose, no markdown fences, no explanation. "
    "Use SQLite-compatible syntax (strftime for date functions)."
)

_SELECT_ONLY_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_FORBIDDEN_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|--|;.*\S)", re.IGNORECASE
)


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
