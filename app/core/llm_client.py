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

def _mock_route(user: str) -> str:  # v5 — bulletproof routing
    u = user.lower()

    # 1. Pure conversation — must match exactly, nothing data-related
    pure_chat = ["hi", "hello", "hey", "good morning", "good afternoon",
                 "what's up", "howdy", "sup", "greetings", "how are you",
                 "thank you", "thanks", "great job", "who are you",
                 "what are you", "what can you do", "who built you",
                 "capabilities", "how do you work", "tell me about yourself"]
    if any(u == g or u.startswith(g + " ") or u.startswith(g + "!") for g in pure_chat):
        return "conversation_agent"

    # 2. Document / HR knowledge — must come before data checks
    doc_signals = ["policy", "entitlement", "sick leave", "annual leave", "vacation",
                   "parental", "maternity", "paternity", "bereavement", "remote work",
                   "wfh", "onboard", "performance review", "appraisal", "hr ",
                   "handbook", "sop", "procedure", "regulation", "compliance",
                   "according to", "what does the document", "leave policy",
                   "carrier performance", "q1", "q2", "q3", "q4", "quarter",
                   "port congestion", "sla", "northroute", "fastfreight", "pacificlink"]
    if any(d in u for d in doc_signals):
        return "knowledge_agent"

    # 3. Analytics — computed insights, not raw rows
    analytics_signals = ["trend", "kpi", "summary", "overview", "insight",
                         "anomaly", "over time", "weekly", "monthly", "performance",
                         "dashboard", "hotspot", "busiest", "worst route", "best route",
                         "most delay", "highest delay", "most delays", "which route",
                         "rate", "percentage", "average delay", "analysis", "report"]
    if any(a in u for a in analytics_signals):
        return "analytics_agent"

    # 4. SQL — anything mentioning show/list/find OR data objects
    data_words = ["shipment", "delay", "cancel", "origin", "destination",
                  "cargo", "route", "status", "toronto", "vancouver", "calgary",
                  "montreal", "chicago", "seattle", "new york", "shipped",
                  "show", "list", "find", "fetch", "display", "count", "how many",
                  "get all", "all delayed", "all cancelled", "all on_time",
                  "recent", "latest", "last month", "last week"]
    if any(d in u for d in data_words):
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
    u = user.lower()
    # HR policy answers
    if "sick" in u:
        return "Employees receive **10 paid sick days per year** with no carryover. A medical certificate is required for sick leave longer than 3 consecutive days. If sick leave is exhausted, employees may apply for unpaid medical leave of up to 30 days with manager and HR approval."
    if "annual leave" in u or "vacation" in u or "holiday" in u:
        return "Full-time employees accrue **20 days of paid annual leave per calendar year**, credited at the start of each quarter (5 days per quarter). Up to 5 unused days may be carried over to the next year — anything beyond that is forfeited on December 31st. Leave cannot be taken in the first 90 days of employment."
    if "parental" in u or "maternity" in u or "paternity" in u:
        return "**Primary caregivers** receive 16 weeks of paid parental leave. **Secondary caregivers** receive 4 weeks of paid parental leave. Leave must commence within 12 months of the birth or adoption of a child."
    if "bereavement" in u:
        return "Employees receive **5 paid bereavement days** for the loss of an immediate family member (spouse, child, parent, sibling), and **2 paid days** for extended family members."
    if "remote" in u or "work from home" in u or "wfh" in u:
        return "Employees may work remotely **up to 3 days per week** with manager approval. Full remote arrangements require VP-level approval and are reviewed quarterly. Core hours of 10am–3pm in the employee's local timezone must be maintained."
    if "performance" in u or "review" in u or "appraisal" in u:
        return "Performance reviews are conducted **bi-annually**: mid-year in June and year-end in December. Compensation adjustments are tied to year-end reviews. Employees receive at least 2 weeks notice before their scheduled review."
    if "onboard" in u or "new employee" in u or "joining" in u:
        return "New employee onboarding steps:\n1. Complete HR intake forms within 3 business days\n2. Set up payroll and benefits within 2 weeks\n3. Complete mandatory compliance training within 30 days\n4. Schedule 90-day goal meeting with your manager\n5. Register for health insurance within 14 days"
    if "leave request" in u or "how to apply" in u or "request leave" in u:
        return "Planned leave must be submitted through the **HR portal at least 5 business days in advance**. During Q4 peak periods (October–December), 10 business days notice is required. Emergency leave must be reported to your manager immediately with formal documentation submitted within 48 hours."
    # Q1 report answers
    if "on-time" in u or "on time" in u or "delivery rate" in u:
        return "Q1 2026 on-time delivery rate was **86%**, slightly below the 90% corporate target. Best performing route: New York → Montreal at 94%. Worst performing: Chicago → Vancouver at only 69% on-time due to port congestion."
    if "vancouver" in u and ("congestion" in u or "delay" in u or "port" in u):
        return "Vancouver port congestion added an average of **2.3 days of delay** to westbound shipments in February and March, caused by labour disputes and increased Asian import volumes. Mitigation: rerouting through Seattle port. Estimated resolution by end of Q2 2026."
    if "q1" in u or "quarter" in u or "q2" in u:
        return "Q1 2026 highlights: shipment volume up **12% QoQ** (1,847 total shipments), revenue up 9% to $4.2M, gross margin 33% (down from 36%). Key risk was Vancouver port congestion. Q2 action items include renegotiating Vancouver SLA terms and piloting a secondary carrier on Calgary–Montreal."
    if "carrier" in u or "fastfreight" in u or "northroute" in u:
        return "**FastFreight Inc.** (primary carrier): 88% SLA compliance. **NorthRoute Logistics** (secondary): underperforming at 79% — contract review scheduled. **PacificLink** (new, onboarded Feb 2026): 85% early compliance on Vancouver routes."
    if "cancel" in u:
        return "Q1 2026 cancellation rate: **3% of total shipments** (56 cancellations). Primary causes: customer-requested holds (42%), carrier capacity issues (35%), customs delays (23%). Rate is consistent with Q4 2025."
    # Generic fallback using context
    return (
        "Based on the retrieved document context from the HR Leave Policy and Q1 Operations Report, "
        "I found relevant information. The documents cover employee leave entitlements (annual, sick, parental, bereavement), "
        "remote work policy, performance reviews, and Q1 2026 shipment performance metrics. "
        "Could you be more specific about what you'd like to know?"
    )
