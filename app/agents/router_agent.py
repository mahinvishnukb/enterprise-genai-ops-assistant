"""
RouterAgent — the "multi-agent system" / "agentic tool calling" feature.

A single /api/chat endpoint takes free-form questions ("What's the leave
policy?" or "Show delayed shipments last month") and must not require the
user to pick which backend handles it. The RouterAgent is a tiny agent whose
only job is classification: given the question, which downstream
agent/tool should handle it?

This mirrors real function/tool calling: in production you'd give the LLM a
JSON schema of tools (`route_to_knowledge_agent()`, `route_to_sql_agent()`)
and let it call one; here the mock/LLM call returns a tool *name* as a
string, which we validate against a registry before dispatching — never
trust a model's output to be a value you're about to use as a dict key or
exec target without checking it first.

This is also the seam where you'd add more agents (AnalyticsAgent,
ReportingAgent) without touching the API layer: register them in
`self.agents`, teach the router prompt about them, done.
"""
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.sql_agent import SQLAgent
from app.core.llm_client import LLMClient

ROUTER_SYSTEM_PROMPT = (
    "ROUTER: Classify the user's question into exactly one of: "
    "'sql_agent' (questions about shipments, operations data, counts, database "
    "queries) or 'knowledge_agent' (questions about policies, documents, reports, "
    "SOPs). Respond with only the tool name."
)


class RouterAgent:
    def __init__(self, knowledge_agent: KnowledgeAgent, sql_agent: SQLAgent, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()
        self.agents = {
            "knowledge_agent": knowledge_agent,
            "sql_agent": sql_agent,
        }

    def classify(self, question: str) -> str:
        raw = self.llm.chat(system=ROUTER_SYSTEM_PROMPT, user=question).strip().lower()
        return raw if raw in self.agents else "knowledge_agent"

    def handle(self, question: str) -> dict:
        target = self.classify(question)
        if target == "sql_agent":
            result = self.agents["sql_agent"].ask(question)
            return {"agent": "sql_agent", **result}
        result = self.agents["knowledge_agent"].answer(question)
        return {"agent": "knowledge_agent", **result}
