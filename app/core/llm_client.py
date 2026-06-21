"""
LLMClient: one seam between "our app logic" and "whichever model vendor we
call today."

CONCEPTS (read this before the interview):

- Tokens: LLMs don't see characters or words, they see tokens (sub-word
  chunks, ~4 chars in English on average). Pricing, context limits, and
  truncation are all measured in tokens, not characters.

- Context window: the max number of tokens (prompt + completion) a model
  can attend to at once. RAG exists largely *because* of this limit — you
  can't paste a 500-page SOP into the prompt, so you retrieve only the
  relevant chunks and inject those instead.

- Prompt engineering: structuring the instructions, role, and examples you
  give the model so it reliably produces the output shape you want (e.g.
  "respond with ONLY a SQL query, no prose" in the SQL agent below).

- Function calling / tool calling: instead of free-text output, you give
  the model a JSON schema of "tools" it can invoke (e.g. run_sql_query(query:
  str)). The model returns structured arguments, your code executes the real
  function, and feeds the result back. This is what turns an LLM into an
  "agent" instead of a chatbot — see router_agent.py.

WHY A MOCK MODE: tests and CI must run with zero API keys and zero network
calls (otherwise CI is flaky, slow, and leaks cost). `LLM_PROVIDER=mock`
returns deterministic, rule-based responses so pytest and GitHub Actions
stay green without a key. Flip to "openai" or "anthropic" once you have a
key, with no code changes elsewhere in the app — that's the point of having
this class as the single seam.
"""
from app.core.config import settings


class LLMClient:
    def __init__(self, provider: str | None = None):
        self.provider = provider or settings.llm_provider

    def chat(self, system: str, user: str, max_tokens: int = 512) -> str:
        """Single entry point every agent uses. Returns the model's text reply."""
        if self.provider == "openai":
            return self._call_openai(system, user, max_tokens)
        if self.provider == "anthropic":
            return self._call_anthropic(system, user, max_tokens)
        return self._call_mock(system, user)

    # --- real providers -----------------------------------------------
    def _call_openai(self, system: str, user: str, max_tokens: int) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    def _call_anthropic(self, system: str, user: str, max_tokens: int) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text

    # --- offline / CI mode ---------------------------------------------
    def _call_mock(self, system: str, user: str) -> str:
        """
        Deterministic stand-in so unit tests assert on real behavior
        (routing, SQL templating, chunk selection) without hitting a network.
        Recognizes a couple of task markers the agents place in `system`.
        """
        if "SQL_GENERATION" in system:
            return _mock_sql(user)
        if "ROUTER" in system:
            return _mock_route(user)
        if "REPORT_GENERATION" in system:
            return "Executive Summary: Operations stable. KPIs nominal. No critical risks detected."
        # Knowledge agent fallback: just echo back the strongest signal so
        # tests can assert the right context chunk was retrieved.
        return f"[mock-answer based on retrieved context] {user[:200]}"


def _mock_sql(user: str) -> str:
    u = user.lower()
    if "delayed shipment" in u or "delay" in u:
        return (
            "SELECT id, origin, destination, delay_days, shipped_at "
            "FROM operations_data WHERE status = 'delayed' "
            "ORDER BY shipped_at DESC LIMIT 50;"
        )
    if "count" in u and "ticket" in u:
        return "SELECT status, COUNT(*) FROM operations_data GROUP BY status;"
    return "SELECT * FROM operations_data ORDER BY shipped_at DESC LIMIT 20;"


def _mock_route(user: str) -> str:
    u = user.lower()
    sql_signals = ["shipment", "query", "database", "count", "row", "table", "sql", "delay"]
    if any(s in u for s in sql_signals):
        return "sql_agent"
    return "knowledge_agent"
