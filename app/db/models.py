"""
SQLAlchemy models — updated to reflect the full Propgatics logistics schema.

Four original application tables (User, Document, ChatMessage, OperationsData)
plus two new domain tables sourced from the Propgatics Logistics Intelligence
Platform: Shipment (100K synthetic rows, 5K seeded) and Incident (25K rows,
1K seeded).  OperationsData is retained for migration safety but is no longer
queried by agents — all SQL/Analytics work targets shipments + incidents.
"""
import datetime as dt

from sqlalchemy import (
    Column, Date, DateTime, Float, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ─── Application tables ───────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    chat_messages = relationship("ChatMessage", back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    doc_id = Column(String, unique=True, nullable=False)
    filename = Column(String, nullable=False)
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=dt.datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    role = Column(String, nullable=False)   # "user" | "assistant"
    agent = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    user = relationship("User", back_populates="chat_messages")


class OperationsData(Base):
    """Legacy placeholder table — kept so existing migrations don't fail.
    New code should query the Shipment and Incident tables instead."""
    __tablename__ = "operations_data"

    id = Column(Integer, primary_key=True)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    status = Column(String, nullable=False)
    delay_days = Column(Integer, default=0)
    shipped_at = Column(Date, nullable=False)


# ─── Propgatics domain tables ─────────────────────────────────────────────────

class Shipment(Base):
    """
    Full shipment lifecycle record.  Sourced from the Propgatics Logistics
    Intelligence Platform (shipments_enriched_dataset.csv, 100K rows).
    5 000 representative rows are seeded on first startup.

    shipment_status values : 'Delivered', 'Delayed', 'Minor Delay',
                              'Critical Delay'
    risk_category values   : 'Low', 'Medium', 'High', 'Critical'
    delivery_performance   : 'On Time', 'Delayed'
    """
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shipment_id = Column(String, unique=True, nullable=False)
    tracking_number = Column(String)
    carrier = Column(String)          # UPS, FedEx, DHL, Canada Post, Purolator
    origin = Column(String)
    destination = Column(String)
    distance_km = Column(Float)
    estimated_duration_hours = Column(Float)
    shipment_date = Column(Date)
    estimated_delivery_date = Column(Date)
    actual_delivery_date = Column(Date)
    shipment_status = Column(String)  # 'Delivered','Delayed','Minor Delay','Critical Delay'
    delay_hours = Column(Float, default=0.0)
    package_weight_kg = Column(Float)
    package_type = Column(String)
    shipping_cost_cad = Column(Float)
    priority_level = Column(String)   # 'Standard','Express','Same-Day'
    service_level = Column(String)    # 'Two-Day','Priority','Economy'
    customer_type = Column(String)    # 'Business','Individual'
    weather_condition = Column(String)
    traffic_level = Column(String)    # 'Low','Medium','High'
    warehouse_id = Column(String)
    driver_id = Column(String)
    fuel_cost_cad = Column(Float)
    delivery_cost_cad = Column(Float)
    delay_reason = Column(String)
    on_time_delivery = Column(Integer)   # 1 = on time, 0 = late
    route_risk_score = Column(Float)
    risk_category = Column(String)       # 'Low','Medium','High','Critical'
    delivery_performance = Column(String)  # 'On Time','Delayed'


class Incident(Base):
    """
    Logistics incident records linked to shipments.  Sourced from the
    Propgatics platform (incidents_dataset.csv, 25K rows).
    1 000 representative rows are seeded on first startup.

    severity_level  : 'Low', 'Medium', 'High', 'Critical'
    incident_status : 'Resolved', 'Under Investigation', 'Open'
    """
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String, unique=True, nullable=False)
    shipment_id = Column(String)
    tracking_number = Column(String)
    carrier = Column(String)
    origin = Column(String)
    destination = Column(String)
    incident_type = Column(String)
    severity_level = Column(String)
    incident_status = Column(String)
    incident_date = Column(String)        # ISO datetime string
    delay_hours = Column(Float)
    weather_condition = Column(String)
    traffic_level = Column(String)
    route_risk_score = Column(Float)
    estimated_financial_loss_cad = Column(Float)
    resolution_action = Column(String)
    resolution_time_hours = Column(Float)
    warehouse_id = Column(String)
    driver_id = Column(String)
