"""
SQLAlchemy models. These four tables map directly to the JD's "Database:
Users, Documents, Chat History, Operations Data" requirement.

Why an ORM instead of raw SQL here (vs. the SQLAgent, which deliberately
generates raw SQL for ad-hoc analyst questions): the *application's own*
read/write paths (saving a chat message, recording an uploaded document)
are fixed and known ahead of time, so a typed model catches bugs at
write-time and gives you migrations (e.g. via Alembic) for free. Ad-hoc
natural-language questions, by contrast, can't be modeled in advance — that
is exactly the problem the SQL agent exists to solve.
"""
import datetime as dt

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


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
    doc_id = Column(String, unique=True, nullable=False)  # matches vector store doc_id
    filename = Column(String, nullable=False)
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=dt.datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    role = Column(String, nullable=False)  # "user" | "assistant"
    agent = Column(String, nullable=True)  # which agent answered: knowledge_agent | sql_agent
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    user = relationship("User", back_populates="chat_messages")


class OperationsData(Base):
    __tablename__ = "operations_data"

    id = Column(Integer, primary_key=True)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    status = Column(String, nullable=False)  # delayed | on_time | cancelled
    delay_days = Column(Integer, default=0)
    shipped_at = Column(Date, nullable=False)
