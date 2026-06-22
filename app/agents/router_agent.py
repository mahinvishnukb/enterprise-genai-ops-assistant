"""
RouterAgent — classifies every incoming message into one of four agents.

Four-way routing lets us handle the full spectrum of enterprise user intents:
  - conversation_agent: greetings, help, meta-questions, follow-ups
  - sql_agent: precise data retrieval (counts, filters, lists)
  - analytics_agent: insights, trends, KPIs, anomalies, summaries
  - knowledge_agent: questions about uploaded documents / policies

Ambiguity handling: a single-shot classification with a silent default is
fine until a message genuinely straddles two agents ("show me the route
performance" could be SQL or analytics). Instead of guessing once and
hoping, the router asks the LLM for a *confidence* score and a second-best
guess in the same call, then:
  - high confidence -> route to the primary agent only, same as before.
  - low confidence  -> still answer with the primary agent (so the user
    always gets a response), but also dispatch to the secondary candidate
    and surface both the confidence and the secondary's answer under a
    `routing` key, so callers (the API response, the UI) can be transparent
    about the ambiguity instead of silently picking one and hiding the
    uncertainty.
"""
from dataclasses import dataclass

from app.agents.analytics_agent import AnalyticsAgent
from app.agents.conversation_agent import ConversationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.sql_agent import SQLAgent
from app.core.llm_client import LLMClient

ROUTER_SYSTEM_PROMPT = (
    "ROUTER: Classify the user's message and respond with EXACTLY three lines, nothing else:\n"
    "Line 1: the single best-matching agent name — one of 'conversation_agent', 'sql_agent', "
    "'analytics_agent', 'knowledge_agent'.\n"
    "Line 2: your confidence that line 1 is the correct single agent, as a number between 0.0 "
    "and 1.0 (1.0 = unambiguous, 0.5 = could plausibly be a different agent, 0.0 = pure guess).\n"
    "Line 3: the second-best-matching agent name if the message could plausibly belong there "
    "too, otherwise the literal word 'none'.\n\n"
    "'conversation_agent' = greetings, help requests, meta questions, small talk, follow-ups "
    "unrelated to data.\n"
    "'sql_agent' = requests to show, list, find, or count specific rows from the database.\n"
    "'analytics_agent' = requests for trends, insights, KPIs, summaries, anomalies, reports, "
    "comparisons over time.\n"
    "'knowledge_agent' = questions about documents, policies, SOPs, reports that were uploaded."
)

# Below this confidence (and only when a distinct secondary candidate
# exists), the router treats the classification as ambiguous and fans out
# to the secondary agent too, rather than silently committing to one guess.
AMBIGUITY_CONFIDENCE_THRESHOLD = 0.55


@dataclass
class RouteDecision:
    primary: str
    confidence: float
    secondary: str | None = None


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

    def classify(self, question: str) -> RouteDecision:
        raw = self.llm.chat(system=ROUTER_SYSTEM_PROMPT, user=question).strip()
        lines = [line.strip().lower() for line in raw.splitlines() if line.strip()]

        primary = lines[0] if lines else "conversation_agent"
        if primary not in self.agents:
            primary = "conversation_agent"

        confidence = 0.5
        if len(lines) > 1:
            try:
                confidence = max(0.0, min(1.0, float(lines[1])))
            except ValueError:
                confidence = 0.5

        secondary = None
        if len(lines) > 2 and lines[2] in self.agents and lines[2] != primary:
            secondary = lines[2]

        return RouteDecision(primary=primary, confidence=confidence, secondary=secondary)

    def _dispatch(self, target: str, question: str, history: list[dict] | None) -> dict:
        if target == "sql_agent":
            return {"agent": "sql_agent", **self.agents["sql_agent"].ask(question)}
        if target == "analytics_agent":
            return {"agent": "analytics_agent", **self.agents["analytics_agent"].compute(question)}
        if target == "knowledge_agent":
            return {"agent": "knowledge_agent", **self.agents["knowledge_agent"].answer(question)}
        return {"agent": "conversation_agent", **self.agents["conversation_agent"].respond(question, history=history)}

    def handle(self, question: str, history: list[dict] | None = None) -> dict:
        decision = self.classify(question)

        # Defensive: classify() is a documented override point in tests (and
        # could be monkeypatched by callers), so handle() must not assume the
        # return value is a well-formed RouteDecision.
        if isinstance(decision, str):
            decision = RouteDecision(primary=decision, confidence=1.0, secondary=None)

        target = decision.primary if decision.primary in self.agents else "conversation_agent"
        result = self._dispatch(target, question, history)

        ambiguous = (
            decision.confidence < AMBIGUITY_CONFIDENCE_THRESHOLD
            and decision.secondary is not None
            and decision.secondary in self.agents
            and decision.secondary != target
        )
        result["routing"] = {"confidence": round(decision.confidence, 2), "ambiguous": ambiguous}

        if ambiguous:
            secondary_result = self._dispatch(decision.secondary, question, history)
            result["routing"]["also_considered"] = decision.secondary
            result["routing"]["secondary_answer"] = secondary_result.get("answer")

        return result
