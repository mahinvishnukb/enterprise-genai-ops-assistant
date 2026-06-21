"""
Engine/session setup. `check_same_thread=False` is only needed for SQLite
(it's a file-based DB that normally refuses cross-thread access, which
FastAPI's per-request threading would otherwise trip over); Postgres in
docker-compose doesn't need it. The `connect_args` dict is built
conditionally so the same code path works for both.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
