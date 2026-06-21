"""
Centralized settings, loaded once from environment variables.

Why this pattern: hard-coding API keys / DB urls in code is both a security
problem (secrets end up in git history) and a portability problem (can't run
the same code in dev, CI, and prod). Pydantic's BaseSettings reads from the
environment (and a local .env file via python-dotenv) and validates types,
so the rest of the app just does `settings.DATABASE_URL` and never touches
os.environ directly.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./local_dev.db")
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_store")


settings = Settings()
