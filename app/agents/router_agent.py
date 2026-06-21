"""
RouterAgent — classifies every incoming message into one of four agents.

Four-way routing lets us handle the full spectrum of enterprise user intents:
  - conversation_agent: greetings, help, meta-questions, follow-ups
  - sql_agent: precise data retrieval (counts, filters, lists)
  - analytics_agent: insights, trends, KPIs, anomalies, summaries
  - knowledge_agent: questions about uploaded documents / policies
"""
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.conversation_agent import ConversationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.sql_agent import SQLAgent
from app.core.llm_client import LLMClient

ROUTER_SYSTEM_PROMPT = (
    "ROUTER: Classify the user's message into exactly one of: "
    "'conversation_agent' (greetings, help requests, meta questions, small talk, follow-ups unrelated to data), "
    "'sql_agent' (requests to show, list, find, or count specific rows from the database), "
    "'analytics_agent' (requests for trends, insights, KPIs, summaries, anomalies, reports, comparisons over time), "
    "'knowledge_agent' (questions about documents, policies, SOPs, reports that were uploaded). "
    "Respond with ONLY the agent name."
)


class RouterAgent:
    def __init__(
        self,
        knowledge_agent: KnowledgeAgent,
        sql_agent: SQLAgent,
        analytics_agent: AnalyticsAgent,
        conversation_agent: ConversationAgent,
        llm: LLMClient | None = None,
    ):
        self.llm = llm or LLMClient()
        self.agents = {
            "knowledge_agent": knowledge_agent,
            "sql_agent": sql_agent,
            "analytics_agent": analytics_agent,
            "conversation_agent": conversation_agent,
        }

    def classify(self, question: str) -> str:
        raw = self.llm.chat(system=ROUTER_SYSTEM_PROMPT, user=question).strip().lower()
        return raw if raw in self.agents else "conversation_agent"

    def handle(self, question: str, history: list[dict] | None = None) -> dict:
        target = self.classify(question)

        if target == "sql_agent":
            result = self.agents["sql_agent"].ask(question)
            return {"agent": "sql_agent", **result}

        if target == "analytics_agent":
            result = self.agents["analytics_agent"].compute(question)
            return {"agent": "analytics_agent", **result}

        if target == "knowledge_agent":
            result = self.agents["knowledge_agent"].answer(question)
            return {"agent": "knowledge_agent", **result}

        result = self.agents["conversation_agent"].respond(question, history=history)
        return {"agent": "conversation_agent", **result}
