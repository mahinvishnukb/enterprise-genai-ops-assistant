"""
Ensures LLM_PROVIDER/DATABASE_URL default to safe offline values before any
app module is imported by pytest, regardless of which test file runs first
or what's in the developer's local .env.
"""
import os

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
