"""
LLMClient: single seam between app logic and the model vendor.

Switch provider via LLM_PROVIDER env var:
  mock      — rich deterministic responses, no API key, used in CI and free deployments
  openai    — GPT-4o-mini via OpenAI SDK
  anthropic — Claude 3.5 Sonnet via Anthropic SDK
"""
import random

from app.core.config import settings


class LLMClient:
    def __init__(self, provider: str | None = None):
        self.provider = provider or settings.llm_provider

    def chat(self, system: str, user: str, max_tokens: int = 1024) -> str:
        if self.provider == "openai":
            return self._call_openai(system, user, max_tokens)
        if self.provider == "anthropic":
            return self._call_anthropic(system, user, max_tokens)
        return self._call_mock(system, user)

    def _call_openai(self, system: str, user: str, max_tokens: int) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""

    def _call_anthropic(self, system: str, user: str, max_tokens: int) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text

    def _call_mock(self, system: str, user: str) -> str:
        if "SQL_GENERATION" in system:
            return _mock_sql(user)
        if "ROUTER" in system:
            return _mock_route(user)
        if "REPORT_GENERATION" in system:
            return _mock_report(user)
        if "CONVERSATION" in system:
            return _mock_conversation(user)
        return _mock_knowledge(user)


# ─── Mock implementations ─────────────────────────────────────────────────────

def _mock_route(user: str) -> str:
    u = user.lower()

    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "what's up", "howdy", "sup", "greetings"]
    meta = ["what can you do", "capabilities", "what are you", "who are you", "how do you work", "tell me about yourself"]
    doc_signals = ["policy", "leave entitlement", "sick leave", "sop", "procedure", "handbook", "regulation", "according to", "what does the document"]
    analytics_signals = ["trend", "kpi", "summary", "overview", "anomaly", "over time", "weekly", "monthly", "performance", "dashboard", "insight", "hotspot", "cancellation rate", "on-time rate", "delay rate", "busiest", "comparison"]
    # explicit data-retrieval patterns
    sql_signals = [
        "show", "list", "fetch", "display", "get all", "find all",
        "how many", "count", "which shipment",
        "delayed shipment", "cancelled shipment", "on_time shipment",
        "shipment from", "shipment to",
        "from chicago", "from seattle", "from toronto", "from vancouver",
        "from calgary", "from montreal", "from new york",
        "to toronto", "to calgary", "to vancouver", "to chicago",
        "to seattle", "to montreal", "to new york",
        "recent shipment", "latest shipment", "last shipment",
        "all delayed", "all cancelled", "all shipment",
    ]

    if any(g in u for g in greetings):
        return "conversation_agent"
    if any(m in u for m in meta):
        return "conversation_agent"
    if any(d in u for d in doc_signals):
        return "knowledge_agent"
    if any(a in u for a in analytics_signals):
        return "analytics_agent"
    if any(s in u for s in sql_signals):
        return "sql_agent"
    # fallback: raw data keywords → sql
    if any(k in u for k in ["shipment", "delay", "cancel", "origin", "destination", "route", "cargo"]):
        return "sql_agent"
    return "conversation_agent"


def _mock_sql(user: str) -> str:
    u = user.lower()
    if "delayed" in u:
        return "SELECT id, origin, destination, delay_days, shipped_at FROM operations_data WHERE status = 'delayed' ORDER BY shipped_at DESC LIMIT 50;"
    if "cancel" in u:
        return "SELECT id, origin, destination, shipped_at FROM operations_data WHERE status = 'cancelled' ORDER BY shipped_at DESC LIMIT 50;"
    if "on_time" in u or "on time" in u:
        return "SELECT id, origin, destination, shipped_at FROM operations_data WHERE status = 'on_time' ORDER BY shipped_at DESC LIMIT 50;"
    if "toronto" in u:
        return "SELECT id, origin, destination, status, delay_days, shipped_at FROM operations_data WHERE destination = 'Toronto' OR origin = 'Toronto' ORDER BY shipped_at DESC LIMIT 50;"
    if "vancouver" in u:
        return "SELECT id, origin, destination, status, delay_days, shipped_at FROM operations_data WHERE destination = 'Vancouver' OR origin = 'Vancouver' ORDER BY shipped_at DESC LIMIT 50;"
    if "chicago" in u:
        return "SELECT id, origin, destination, status, delay_days, shipped_at FROM operations_data WHERE origin = 'Chicago' OR destination = 'Chicago' ORDER BY shipped_at DESC LIMIT 50;"
    if "count" in u or "how many" in u:
        return "SELECT status, COUNT(*) as count FROM operations_data GROUP BY status ORDER BY count DESC;"
    if "recent" in u or "latest" in u or "last" in u:
        return "SELECT id, origin, destination, status, delay_days, shipped_at FROM operations_data ORDER BY shipped_at DESC LIMIT 20;"
    if "worst" in u or "most delay" in u:
        return "SELECT origin, destination, COUNT(*) as delay_count, AVG(delay_days) as avg_delay FROM operations_data WHERE status='delayed' GROUP BY origin, destination ORDER BY delay_count DESC LIMIT 10;"
    return "SELECT id, origin, destination, status, delay_days, shipped_at FROM operations_data ORDER BY shipped_at DESC LIMIT 20;"


def _mock_report(user: str) -> str:
    u = user.lower()
    if "kpi" in u or "summary" in u:
        return (
            "Operations are performing at a moderate efficiency level. "
            "Approximately 25% of shipments are experiencing delays, with an average delay of 4 days — "
            "this is above the industry benchmark of 15% and warrants immediate attention on high-traffic routes. "
            "Cancellations remain low at under 10%, which is within acceptable thresholds. "
            "Focus remediation efforts on the Chicago–Montreal and Seattle–Toronto corridors, which show the highest delay concentrations."
        )
    if "delay" in u:
        return (
            "Delay analysis reveals a concentration of late shipments on cross-border routes, "
            "particularly those involving Chicago and Seattle as origin cities. "
            "The Chicago → Montreal route is the single highest-risk corridor with a delay rate exceeding 30%. "
            "Average delay duration is 4.2 days across all affected shipments. "
            "Recommend reviewing carrier SLAs and introducing buffer time on these routes."
        )
    if "route" in u or "popular" in u:
        return (
            "Route analysis shows that Toronto, Vancouver, and Calgary are the highest-volume destination cities. "
            "The busiest corridor sees roughly 18–22 shipments per month. "
            "Routes involving New York as origin show the best on-time performance at over 80%. "
            "Consider capacity rebalancing from underperforming routes to high-demand corridors."
        )
    if "trend" in u or "week" in u:
        return (
            "Weekly trend analysis shows shipment volumes are stable with slight week-over-week variance of ±8%. "
            "Delay rates peaked three weeks ago and have shown a modest improvement of 5% since then. "
            "This improvement correlates with a reduction in Chicago-origin shipments, suggesting a carrier or routing change may have had positive effects. "
            "Continue monitoring to confirm the trend."
        )
    if "cancel" in u:
        return (
            "Cancellation rates are within normal bounds at approximately 8% of total shipments. "
            "Montreal and Calgary show the highest cancellation origination rates. "
            "No single cause has been isolated — recommend cross-referencing with carrier incident logs to identify root causes. "
            "If rates exceed 12%, consider issuing a formal vendor performance review."
        )
    return (
        "Overall operations summary: 120 shipments recorded over the past 60 days across 7 major cities. "
        "On-time performance sits at approximately 67%, with delays and cancellations accounting for the remainder. "
        "Key risk areas are the Chicago–Montreal and Seattle–Toronto corridors. "
        "Recommend a targeted carrier review and SLA renegotiation for Q3."
    )


def _mock_conversation(user: str) -> str:
    u = user.lower()

    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "howdy"]
    if any(g in u for g in greetings):
        return random.choice([
            "Hello! I'm your Enterprise GenAI Operations Assistant. I can help you with:\n\n"
            "• **Operations data** — query shipments, delays, routes, and cancellations\n"
            "• **Analytics & insights** — trends, KPIs, delay hotspots, weekly reports\n"
            "• **Document knowledge** — answer questions from uploaded policies and SOPs\n\n"
            "Try asking: *\"Show delayed shipments\"*, *\"What's our on-time rate?\"*, or upload an HR policy and ask about it.",

            "Hi there! I'm your AI operations co-pilot. Ask me anything about your shipment data, "
            "request an analytics summary, or upload a document and query it. What would you like to explore?",
        ])

    if any(w in u for w in ["what can you do", "capabilities", "help", "how do you work", "what are you"]):
        return (
            "I'm a multi-agent AI assistant with four specialized capabilities:\n\n"
            "**1. SQL Agent** — retrieves precise data from your operations database\n"
            "   → *\"Show all delayed shipments from Chicago\"*\n\n"
            "**2. Analytics Agent** — computes trends, KPIs, and anomaly detection\n"
            "   → *\"What's our delay trend over the past month?\"*\n\n"
            "**3. Knowledge Agent** — answers questions from uploaded documents\n"
            "   → *\"What is the annual leave policy?\"* (after uploading HR docs)\n\n"
            "**4. Conversation Agent** — that's me! I handle everything else.\n\n"
            "Your questions are automatically routed to the right agent — you don't need to specify which one."
        )

    if any(w in u for w in ["thank", "thanks", "great", "awesome", "nice", "good job", "perfect"]):
        return random.choice([
            "You're welcome! Let me know if there's anything else I can help you analyze.",
            "Happy to help! Feel free to ask anything else about your operations data or documents.",
            "Glad that was useful! What else would you like to explore?",
        ])

    if any(w in u for w in ["who built", "who made", "who created", "what is this"]):
        return (
            "This is the **Enterprise GenAI Operations Assistant** — a production-grade multi-agent AI platform "
            "built with FastAPI, React, and a multi-agent architecture (Router → SQL/Analytics/Knowledge/Conversation agents). "
            "It supports natural language querying over structured databases (NL2SQL) and unstructured documents (RAG), "
            "with pluggable LLM providers (OpenAI, Anthropic, or mock mode)."
        )

    if any(w in u for w in ["how are you", "how's it going", "how are things"]):
        return "I'm running smoothly and ready to help! What can I analyze for you today?"

    if "?" not in u and len(u.split()) <= 3:
        return (
            f"I received your message: *\"{user}\"*. Could you be more specific? "
            "You can ask me to show shipment data, run analytics, or query an uploaded document. "
            "Type *\"help\"* to see everything I can do."
        )

    return (
        f"I want to make sure I give you the most accurate answer. Could you clarify what you're looking for?\n\n"
        "Here are some things I can help with:\n"
        "• **Data queries**: *\"Show all shipments to Vancouver this month\"*\n"
        "• **Analytics**: *\"What's the delay rate by route?\"*\n"
        "• **Documents**: Upload a file and ask about its contents\n"
        "• **Reports**: *\"Give me a KPI summary\"*"
    )


def _mock_knowledge(user: str) -> str:
    return (
        "Based on the retrieved document context, here is what I found:\n\n"
        "The document addresses this topic in detail. Please ensure you have uploaded the relevant "
        "document using the Upload button in the sidebar — once ingested, I can give you a precise, "
        "grounded answer with source citations."
    )
