"""
LLMClient: single seam between app logic and the model vendor.

Switch provider via LLM_PROVIDER env var:
  groq      — llama-3.3-70b-versatile via Groq API (FREE, 6 000 req/day, fastest)
  openai    — GPT-4o-mini via OpenAI SDK
  anthropic — Claude 3.5 Sonnet via Anthropic SDK
  mock      — rich deterministic fallback, no API key required

Groq is the recommended free tier: sign up at console.groq.com, copy the key
to GROQ_API_KEY in your Render environment, set LLM_PROVIDER=groq.
"""
import random

from app.core.config import settings


class LLMClient:
    def __init__(self, provider: str | None = None):
        self.provider = provider or settings.llm_provider

    def chat(self, system: str, user: str, max_tokens: int = 1024) -> str:
        if self.provider == "groq":
            return self._call_groq(system, user, max_tokens)
        if self.provider == "openai":
            return self._call_openai(system, user, max_tokens)
        if self.provider == "anthropic":
            return self._call_anthropic(system, user, max_tokens)
        return self._call_mock(system, user)

    # ── Real providers ────────────────────────────────────────────────────────

    def _call_groq(self, system: str, user: str, max_tokens: int) -> str:
        """Groq: free tier, llama-3.3-70b — fully dynamic AI responses."""
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=max_tokens,
            temperature=0.4,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

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

    # ── Mock fallback ─────────────────────────────────────────────────────────

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
    """Returns a 3-line string:
    line 1 = best agent name
    line 2 = confidence (0.0–1.0)
    line 3 = second-best agent or 'none'
    Confidence is proportional to how decisively one category's keywords won.
    Signal lists are intentionally exhaustive — every plausible English phrasing
    should hit at least one bucket so no question gets silently dropped to
    conversation_agent.
    """
    u = user.lower()

    # ── Exact-match pure chat ──────────────────────────────────────────────────
    pure_chat = [
        "hi", "hello", "hey", "good morning", "good afternoon",
        "what's up", "howdy", "sup", "greetings", "how are you",
        "thank you", "thanks", "great job", "who are you",
        "what are you", "what can you do", "who built you",
        "capabilities", "how do you work", "tell me about yourself",
        "bye", "goodbye", "see you", "exit", "quit",
    ]
    pure_chat_hit = any(u == g or u.startswith(g + " ") or u.startswith(g + "!") for g in pure_chat)

    # ── Knowledge / document signals ──────────────────────────────────────────
    doc_signals = [
        # HR / policy
        "policy", "entitlement", "sick leave", "annual leave", "vacation",
        "parental", "maternity", "paternity", "bereavement", "remote work",
        "wfh", "onboard", "performance review", "appraisal", "hr ",
        "handbook", "sop", "procedure", "regulation", "compliance",
        "according to", "what does the document", "leave policy",
        # Platform / methodology
        "propgatics", "platform", "ors", "openrouteservice",
        "how was the data", "methodology", "how does it work",
        "how was it built", "how is it built", "dataset generated",
        "carrier performance report", "q1 report", "q2 report",
        "port congestion", "sla", "northroute", "fastfreight", "pacificlink",
        "what is the platform", "explain the platform", "about propgatics",
        "history of propgatics", "how many carriers", "how many cities",
        "full dataset", "100k", "100,000", "25k", "25,000",
    ]

    # ── Analytics signals — aggregate insights, KPIs, trends ─────────────────
    analytics_signals = [
        # KPI / summary
        "kpi", "summary", "overview", "dashboard", "insight", "metric",
        "performance", "benchmark", "sla", "scorecard", "executive",
        # Trend / time-based
        "trend", "over time", "weekly", "monthly", "quarterly", "seasonal",
        "year over year", "annually", "time series", "growth", "decline",
        "month by month", "week by week", "day over day", "history",
        "historical", "period", "last quarter", "last year",
        # Comparison & ranking
        "compare", "comparison", "vs", "versus", "ranking", "ranked",
        "top 5", "top 10", "bottom 5", "best", "worst",
        "best performing", "worst performing", "leading", "lagging",
        "outperform", "underperform", "highest performing", "lowest performing",
        # Percentages & rates
        "rate", "percentage", "percent", "%", "proportion", "fraction",
        "average", "mean", "median", "distribution", "spread",
        # Route & carrier analytics
        "hotspot", "busiest", "slowest carrier", "fastest carrier",
        "worst route", "best route", "busiest route", "top routes",
        "most delays", "highest delay", "most delay", "lowest delay",
        "carrier performance", "carrier comparison", "carrier benchmark",
        "on-time rate", "on-time performance", "delivery rate",
        "delivery performance", "which carrier",
        # Financial analytics
        "revenue", "profitability", "roi", "cost per", "total cost",
        "average cost", "financial loss", "financial impact", "financial",
        "shipping spend", "cost efficiency", "cost analysis", "spend",
        "cost breakdown", "freight cost",
        # Risk analytics
        "risk score", "risk profile", "risk distribution", "risk analysis",
        "risk by route", "risk by carrier", "risk category",
        # Incident analytics
        "incident rate", "incident type", "incident breakdown",
        "incident analysis", "incident summary", "incident report",
        "top incident", "most common incident", "incident frequency",
        "incident severity", "severity distribution",
        "by severity", "by incident", "by type", "incident trend",
        "resolution time", "avg resolution", "financial impact of",
        # Weather & ops analytics
        "weather impact", "weather analysis", "weather effect",
        "traffic impact", "traffic analysis",
        # Efficiency
        "efficiency", "throughput", "capacity", "utilisation", "utilization",
        "operational performance", "ops performance",
        # Open-ended phrasing
        "analysis", "report", "breakdown", "anomaly", "outlier", "pattern",
        "how does", "how is our", "how many percent", "how has",
        "what percentage", "what proportion", "what is the average",
        "what is the rate", "what is the trend", "what is the distribution",
        "which route has", "which month", "which week", "which day",
        "over the last", "in the last", "since last",
        # Specific analytics question starters
        "give me a summary", "give me an overview", "give me insights",
        "show me trends", "show me performance", "show me analytics",
        "analyze", "analyse", "breakdown of", "breakdown by",
    ]

    # ── SQL signals — show/list/find raw rows from the DB ────────────────────
    data_words = [
        # Core entity words
        "shipment", "shipments", "incident", "incidents",
        "package", "parcel", "freight", "order", "orders",
        # Carrier names
        "ups", "fedex", "dhl", "canada post", "purolator", "carrier",
        # Status words
        "delayed", "delay", "critical delay", "minor delay",
        "delivered", "cancelled", "cancel", "overdue", "late", "on time", "on-time",
        # All cities
        "toronto", "vancouver", "calgary", "montreal", "edmonton",
        "halifax", "moncton", "ottawa", "kelowna", "winnipeg",
        "origin", "destination", "route",
        # Action commands
        "show", "list", "find", "fetch", "display", "give me", "show me",
        "get me", "retrieve", "pull", "get all", "look up", "lookup",
        "count", "how many", "number of", "total number",
        # Data-specific identifiers
        "tracking", "tracking number", "shipment id", "shipment #",
        "status", "driver", "warehouse", "driver id",
        # Risk (raw row level)
        "high risk", "low risk", "medium risk", "risk category", "critical risk",
        # Time filters for listing
        "recent", "latest", "last", "today", "this week", "this month",
        "yesterday", "last 7 days", "last 30 days", "last week", "last month",
        "this year", "past week", "past month",
        # Package / service types (raw row filters)
        "priority", "express", "same-day", "same day", "standard", "economy",
        "overnight", "two-day",
        # Customer types (raw row filters)
        "business customer", "individual customer", "customer type",
        "business shipment", "retail",
        # Package types (raw row filters)
        "small parcel", "large parcel", "pallet", "envelope",
        "weight", "package weight", "heavy",
        # Cost filters (raw listing)
        "most expensive", "cheapest", "lowest cost", "highest cost",
        "expensive shipment", "costly",
        # Open / unresolved
        "open incident", "unresolved", "under investigation",
        "pending", "active incident",
    ]

    def votes(keywords: list[str]) -> int:
        return sum(1 for k in keywords if k in u)

    scores = {
        "conversation_agent": 3 if pure_chat_hit else 0,
        "knowledge_agent": votes(doc_signals),
        "analytics_agent": votes(analytics_signals),
        "sql_agent": votes(data_words),
    }
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    primary, primary_votes = ranked[0]
    secondary, secondary_votes = ranked[1]

    if primary_votes == 0:
        return "conversation_agent\n0.9\nnone"
    if secondary_votes == 0:
        return f"{primary}\n0.95\nnone"

    confidence = round(primary_votes / (primary_votes + secondary_votes), 2)
    confidence = max(0.5, min(confidence, 0.97))
    return f"{primary}\n{confidence}\n{secondary}"


def _mock_sql(user: str) -> str:
    """Generate deterministic SQL against the shipments / incidents schema.
    Covers every plausible English phrasing for row-level data queries.
    """
    u = user.lower()
    cities = [
        "toronto", "vancouver", "calgary", "montreal", "edmonton",
        "halifax", "moncton", "ottawa", "kelowna", "winnipeg",
    ]
    carriers = ["ups", "fedex", "dhl", "canada post", "purolator"]

    # ── Incident queries ───────────────────────────────────────────────────────
    if "incident" in u:
        # Severity / critical
        if any(w in u for w in ["critical", "severity", "high severity", "severe"]):
            return (
                "SELECT incident_id, carrier, origin, destination, incident_type, "
                "severity_level, estimated_financial_loss_cad, incident_status "
                "FROM incidents WHERE severity_level IN ('Critical','High') "
                "ORDER BY estimated_financial_loss_cad DESC LIMIT 20;"
            )
        # Open / unresolved
        if any(w in u for w in ["unresolved", "open", "investigation", "pending", "active"]):
            return (
                "SELECT incident_id, carrier, incident_type, severity_level, "
                "incident_status, delay_hours FROM incidents "
                "WHERE incident_status != 'Resolved' ORDER BY delay_hours DESC LIMIT 20;"
            )
        # Financial / cost / loss
        if any(w in u for w in ["financial", "loss", "cost", "expensive", "revenue"]):
            return (
                "SELECT carrier, COUNT(*) as incidents, "
                "ROUND(SUM(estimated_financial_loss_cad),2) as total_loss_cad, "
                "ROUND(AVG(estimated_financial_loss_cad),2) as avg_loss_cad "
                "FROM incidents GROUP BY carrier ORDER BY total_loss_cad DESC;"
            )
        # Type / breakdown / top
        if any(w in u for w in ["type", "top", "breakdown", "by type", "most common",
                                  "common", "frequent", "frequency"]):
            return (
                "SELECT incident_type, COUNT(*) as count, "
                "ROUND(AVG(estimated_financial_loss_cad),2) as avg_loss_cad, "
                "ROUND(AVG(resolution_time_hours),2) as avg_resolution_hours "
                "FROM incidents GROUP BY incident_type ORDER BY count DESC;"
            )
        # Resolution time
        if any(w in u for w in ["resolution", "resolve", "resolved", "time to fix"]):
            return (
                "SELECT incident_type, "
                "ROUND(AVG(resolution_time_hours),2) as avg_resolution_h, "
                "COUNT(*) as count "
                "FROM incidents WHERE incident_status = 'Resolved' "
                "GROUP BY incident_type ORDER BY avg_resolution_h DESC;"
            )
        # By carrier
        if any(w in u for w in ["by carrier", "carrier", "per carrier"]) or \
                any(c in u for c in carriers):
            for c in carriers:
                if c in u:
                    cap = c.title()
                    return (
                        f"SELECT incident_id, incident_type, severity_level, incident_status, "
                        f"delay_hours, estimated_financial_loss_cad FROM incidents "
                        f"WHERE carrier = '{cap}' ORDER BY estimated_financial_loss_cad DESC LIMIT 20;"
                    )
            return (
                "SELECT carrier, COUNT(*) as incidents, "
                "ROUND(AVG(estimated_financial_loss_cad),2) as avg_loss_cad, "
                "ROUND(AVG(resolution_time_hours),2) as avg_resolution_hours "
                "FROM incidents GROUP BY carrier ORDER BY incidents DESC;"
            )
        # City-specific incidents
        for city in cities:
            if city in u:
                cap = city.title()
                return (
                    f"SELECT incident_id, carrier, origin, destination, incident_type, "
                    f"severity_level, incident_status, delay_hours "
                    f"FROM incidents WHERE origin = '{cap}' OR destination = '{cap}' "
                    f"ORDER BY delay_hours DESC LIMIT 20;"
                )
        # Default incident listing
        return (
            "SELECT incident_id, carrier, origin, destination, incident_type, "
            "severity_level, incident_status, delay_hours, estimated_financial_loss_cad "
            "FROM incidents ORDER BY estimated_financial_loss_cad DESC LIMIT 30;"
        )

    # ── Count / aggregate queries ──────────────────────────────────────────────
    if any(w in u for w in ["how many", "count", "number of", "total number"]):
        if any(w in u for w in ["delayed", "delay", "late"]):
            return (
                "SELECT COUNT(*) as delayed_count FROM shipments "
                "WHERE shipment_status IN ('Delayed', 'Minor Delay', 'Critical Delay');"
            )
        if "critical delay" in u:
            return "SELECT COUNT(*) as critical_delay_count FROM shipments WHERE shipment_status = 'Critical Delay';"
        if any(w in u for w in ["cancel", "cancelled"]):
            return "SELECT COUNT(*) as cancelled_count FROM shipments WHERE shipment_status = 'Cancelled';"
        if any(w in u for w in ["delivered", "on time", "on-time"]):
            return "SELECT COUNT(*) as delivered_count FROM shipments WHERE shipment_status = 'Delivered';"
        if any(w in u for w in ["high risk", "critical risk"]):
            return "SELECT COUNT(*) as high_risk_count FROM shipments WHERE risk_category IN ('High','Critical');"
        # Carrier-specific count
        for c in carriers:
            if c in u:
                cap = c.title()
                return f"SELECT COUNT(*) as count FROM shipments WHERE carrier = '{cap}';"
        # City-specific count
        for city in cities:
            if city in u:
                cap = city.title()
                return (
                    f"SELECT COUNT(*) as count FROM shipments "
                    f"WHERE destination = '{cap}' OR origin = '{cap}';"
                )
        return "SELECT shipment_status, COUNT(*) as count FROM shipments GROUP BY shipment_status ORDER BY count DESC;"

    # ── Carrier-specific queries ───────────────────────────────────────────────
    for carrier in carriers:
        if carrier in u:
            cap = carrier.title()
            if any(w in u for w in ["delay", "delayed", "late"]):
                return (
                    f"SELECT shipment_id, origin, destination, shipment_status, "
                    f"delay_hours, delay_reason, shipment_date FROM shipments "
                    f"WHERE carrier = '{cap}' AND shipment_status IN ('Delayed','Minor Delay','Critical Delay') "
                    f"ORDER BY delay_hours DESC LIMIT 30;"
                )
            if any(w in u for w in ["performance", "on-time", "on time", "rate", "kpi"]):
                return (
                    f"SELECT carrier, COUNT(*) as total, SUM(on_time_delivery) as on_time, "
                    f"ROUND(AVG(on_time_delivery)*100,1) as on_time_pct, "
                    f"ROUND(AVG(delay_hours),2) as avg_delay_hours "
                    f"FROM shipments WHERE carrier = '{cap}' GROUP BY carrier;"
                )
            if any(w in u for w in ["critical", "critical delay"]):
                return (
                    f"SELECT shipment_id, origin, destination, shipment_status, delay_hours, shipment_date "
                    f"FROM shipments WHERE carrier = '{cap}' AND shipment_status = 'Critical Delay' "
                    f"ORDER BY delay_hours DESC LIMIT 20;"
                )
            if any(w in u for w in ["cost", "expensive", "price", "shipping cost"]):
                return (
                    f"SELECT shipment_id, origin, destination, shipping_cost_cad, "
                    f"delivery_cost_cad, shipment_status FROM shipments "
                    f"WHERE carrier = '{cap}' ORDER BY shipping_cost_cad DESC LIMIT 20;"
                )
            return (
                f"SELECT shipment_id, origin, destination, shipment_status, "
                f"delay_hours, shipping_cost_cad, shipment_date FROM shipments "
                f"WHERE carrier = '{cap}' ORDER BY shipment_date DESC LIMIT 30;"
            )

    # ── Risk queries ──────────────────────────────────────────────────────────
    if any(w in u for w in ["high risk", "critical risk"]):
        return (
            "SELECT shipment_id, carrier, origin, destination, route_risk_score, "
            "risk_category, shipment_status FROM shipments "
            "WHERE risk_category IN ('High','Critical') ORDER BY route_risk_score DESC LIMIT 30;"
        )
    if "low risk" in u:
        return (
            "SELECT shipment_id, carrier, origin, destination, route_risk_score, risk_category "
            "FROM shipments WHERE risk_category = 'Low' ORDER BY shipment_date DESC LIMIT 30;"
        )
    if any(w in u for w in ["risk"]):
        return (
            "SELECT risk_category, COUNT(*) as count, "
            "ROUND(AVG(route_risk_score),2) as avg_risk_score "
            "FROM shipments GROUP BY risk_category ORDER BY avg_risk_score DESC;"
        )

    # ── Weather queries ────────────────────────────────────────────────────────
    if "weather" in u:
        for condition in ["storm", "snow", "rain", "fog", "cloudy", "clear"]:
            if condition in u:
                cap = condition.title()
                return (
                    f"SELECT shipment_id, carrier, origin, destination, shipment_status, "
                    f"delay_hours, shipment_date FROM shipments "
                    f"WHERE weather_condition = '{cap}' ORDER BY delay_hours DESC LIMIT 30;"
                )
        return (
            "SELECT weather_condition, COUNT(*) as shipments, "
            "SUM(CASE WHEN shipment_status IN ('Delayed','Minor Delay','Critical Delay') THEN 1 ELSE 0 END) as delays, "
            "ROUND(AVG(delay_hours),2) as avg_delay "
            "FROM shipments GROUP BY weather_condition ORDER BY delays DESC;"
        )

    # ── Traffic queries ────────────────────────────────────────────────────────
    if "traffic" in u:
        return (
            "SELECT traffic_level, COUNT(*) as shipments, "
            "ROUND(AVG(delay_hours),2) as avg_delay_hours, "
            "SUM(CASE WHEN shipment_status IN ('Delayed','Minor Delay','Critical Delay') THEN 1 ELSE 0 END) as delays "
            "FROM shipments GROUP BY traffic_level ORDER BY avg_delay_hours DESC;"
        )

    # ── Priority / service level ───────────────────────────────────────────────
    if any(w in u for w in ["priority", "express", "same-day", "same day", "overnight", "economy", "two-day"]):
        return (
            "SELECT priority_level, service_level, COUNT(*) as count, "
            "ROUND(AVG(delay_hours),2) as avg_delay_hours, "
            "ROUND(AVG(on_time_delivery)*100,1) as on_time_pct "
            "FROM shipments GROUP BY priority_level, service_level ORDER BY on_time_pct DESC;"
        )

    # ── Customer type ─────────────────────────────────────────────────────────
    if any(w in u for w in ["customer type", "business customer", "individual customer",
                              "business shipment", "retail"]):
        return (
            "SELECT customer_type, COUNT(*) as count, "
            "ROUND(AVG(on_time_delivery)*100,1) as on_time_pct, "
            "ROUND(AVG(delay_hours),2) as avg_delay_hours, "
            "ROUND(AVG(shipping_cost_cad),2) as avg_cost_cad "
            "FROM shipments GROUP BY customer_type ORDER BY count DESC;"
        )

    # ── Package type ──────────────────────────────────────────────────────────
    if any(w in u for w in ["package type", "small parcel", "large parcel", "pallet", "envelope", "parcel type"]):
        return (
            "SELECT package_type, COUNT(*) as count, "
            "ROUND(AVG(package_weight_kg),2) as avg_weight_kg, "
            "ROUND(AVG(shipping_cost_cad),2) as avg_cost_cad "
            "FROM shipments GROUP BY package_type ORDER BY count DESC;"
        )

    # ── Most expensive / cost queries ─────────────────────────────────────────
    if any(w in u for w in ["most expensive", "expensive", "highest cost", "costly", "highest shipping"]):
        return (
            "SELECT shipment_id, carrier, origin, destination, "
            "shipping_cost_cad, delivery_cost_cad, shipment_status "
            "FROM shipments ORDER BY shipping_cost_cad DESC LIMIT 20;"
        )
    if any(w in u for w in ["cheapest", "lowest cost", "cheapest route"]):
        return (
            "SELECT shipment_id, carrier, origin, destination, "
            "shipping_cost_cad, shipment_status FROM shipments "
            "ORDER BY shipping_cost_cad ASC LIMIT 20;"
        )

    # ── Worst / best routes ───────────────────────────────────────────────────
    if any(w in u for w in ["worst", "most delay", "highest delay", "most delayed route"]):
        return (
            "SELECT origin, destination, COUNT(*) as total, "
            "SUM(CASE WHEN shipment_status IN ('Delayed','Minor Delay','Critical Delay') THEN 1 ELSE 0 END) as delays, "
            "ROUND(AVG(delay_hours),2) as avg_delay_hours "
            "FROM shipments GROUP BY origin, destination "
            "HAVING delays > 0 ORDER BY avg_delay_hours DESC LIMIT 10;"
        )
    if any(w in u for w in ["best route", "fastest", "best performing route"]):
        return (
            "SELECT origin, destination, COUNT(*) as total, "
            "ROUND(AVG(on_time_delivery)*100,1) as on_time_pct, "
            "ROUND(AVG(delay_hours),2) as avg_delay_hours "
            "FROM shipments GROUP BY origin, destination ORDER BY on_time_pct DESC LIMIT 10;"
        )
    if any(w in u for w in ["on-time", "on time"]) and "carrier" not in u:
        return (
            "SELECT carrier, ROUND(AVG(on_time_delivery)*100,1) as on_time_pct, "
            "ROUND(AVG(delay_hours),2) as avg_delay_hours "
            "FROM shipments GROUP BY carrier ORDER BY on_time_pct DESC;"
        )

    # ── Critical delay (status, not risk) ─────────────────────────────────────
    if "critical delay" in u or ("critical" in u and "delay" in u):
        return (
            "SELECT shipment_id, carrier, origin, destination, "
            "delay_hours, delay_reason, shipment_date FROM shipments "
            "WHERE shipment_status = 'Critical Delay' ORDER BY delay_hours DESC LIMIT 30;"
        )

    # ── Delayed shipments ─────────────────────────────────────────────────────
    if any(w in u for w in ["delayed", "delay", "late", "overdue"]):
        for city in cities:
            if city in u:
                cap = city.title()
                return (
                    f"SELECT shipment_id, carrier, origin, destination, shipment_status, "
                    f"delay_hours, delay_reason, shipment_date FROM shipments "
                    f"WHERE shipment_status IN ('Delayed','Minor Delay','Critical Delay') "
                    f"AND (origin='{cap}' OR destination='{cap}') "
                    f"ORDER BY delay_hours DESC LIMIT 30;"
                )
        return (
            "SELECT shipment_id, carrier, origin, destination, shipment_status, "
            "delay_hours, delay_reason, shipment_date FROM shipments "
            "WHERE shipment_status IN ('Delayed','Minor Delay','Critical Delay') "
            "ORDER BY delay_hours DESC LIMIT 50;"
        )

    # ── Delivered shipments ───────────────────────────────────────────────────
    if any(w in u for w in ["delivered", "on time", "on-time"]):
        for city in cities:
            if city in u:
                cap = city.title()
                return (
                    f"SELECT shipment_id, carrier, origin, destination, "
                    f"actual_delivery_date, shipping_cost_cad FROM shipments "
                    f"WHERE shipment_status = 'Delivered' "
                    f"AND (origin='{cap}' OR destination='{cap}') LIMIT 30;"
                )
        return (
            "SELECT shipment_id, carrier, origin, destination, "
            "actual_delivery_date, shipping_cost_cad, shipment_date FROM shipments "
            "WHERE shipment_status = 'Delivered' ORDER BY shipment_date DESC LIMIT 30;"
        )

    # ── City-specific queries ─────────────────────────────────────────────────
    for city in cities:
        if city in u:
            cap = city.title()
            if "from" in u:
                direction = f"WHERE origin = '{cap}'"
            elif "to" in u:
                direction = f"WHERE destination = '{cap}'"
            else:
                direction = f"WHERE origin = '{cap}' OR destination = '{cap}'"
            return (
                f"SELECT shipment_id, carrier, origin, destination, "
                f"shipment_status, delay_hours, shipment_date FROM shipments "
                f"{direction} ORDER BY shipment_date DESC LIMIT 30;"
            )

    # ── Route summary ─────────────────────────────────────────────────────────
    if "route" in u:
        return (
            "SELECT origin, destination, COUNT(*) as shipments, "
            "ROUND(AVG(delay_hours),2) as avg_delay, "
            "ROUND(AVG(on_time_delivery)*100,1) as on_time_pct "
            "FROM shipments GROUP BY origin, destination ORDER BY shipments DESC LIMIT 15;"
        )

    # ── Status breakdown ──────────────────────────────────────────────────────
    if any(w in u for w in ["by status", "status breakdown", "shipment status", "status distribution"]):
        return (
            "SELECT shipment_status, COUNT(*) as count, "
            "ROUND(AVG(delay_hours),2) as avg_delay_hours "
            "FROM shipments GROUP BY shipment_status ORDER BY count DESC;"
        )

    # ── Carrier breakdown ─────────────────────────────────────────────────────
    if any(w in u for w in ["carrier", "by carrier", "per carrier"]):
        return (
            "SELECT carrier, COUNT(*) as total_shipments, "
            "ROUND(AVG(on_time_delivery)*100,1) as on_time_pct, "
            "ROUND(AVG(delay_hours),2) as avg_delay_hours, "
            "ROUND(AVG(shipping_cost_cad),2) as avg_cost_cad "
            "FROM shipments GROUP BY carrier ORDER BY on_time_pct DESC;"
        )

    # ── Recent / latest / default ─────────────────────────────────────────────
    if any(w in u for w in ["recent", "latest", "last", "today", "this week", "this month"]):
        return (
            "SELECT shipment_id, carrier, origin, destination, shipment_status, "
            "delay_hours, shipment_date FROM shipments ORDER BY shipment_date DESC LIMIT 20;"
        )

    return (
        "SELECT shipment_id, carrier, origin, destination, shipment_status, "
        "delay_hours, shipping_cost_cad, shipment_date "
        "FROM shipments ORDER BY shipment_date DESC LIMIT 20;"
    )


def _mock_report(user: str) -> str:
    """Narrate analytics findings using real Propgatics platform numbers.
    Covers every plausible analytics question type.
    """
    u = user.lower()

    # ── KPI / summary / overview ──────────────────────────────────────────────
    if any(w in u for w in ["kpi", "summary", "overview", "dashboard", "executive", "scorecard"]):
        return (
            "The Propgatics platform is tracking 100,000 shipments across five major Canadian carriers. "
            "Overall on-time delivery stands at 75.26%, with 24.74% of shipments experiencing some form "
            "of delay — above the 85% industry benchmark, signalling a need for carrier SLA review. "
            "Average delay duration is 2.52 hours across affected shipments. "
            "FedEx has the lowest on-time rate at 74.96%, while Canada Post leads at 75.59% — "
            "a narrow 0.63pp spread confirming systemic rather than carrier-specific issues. "
            "Total shipping revenue is CAD $7.43M against delivery costs of CAD $18.86M (2.5× coverage ratio). "
            "25,000 incidents recorded; Failed Delivery Attempt is the most common at 28%. "
            "Action required: SLA renegotiation and weather-aware dynamic routing for Q3."
        )

    # ── Carrier performance ───────────────────────────────────────────────────
    if any(w in u for w in ["carrier", "performance", "compare carrier", "carrier comparison",
                              "carrier benchmark", "carrier ranking"]):
        return (
            "Carrier performance across 100,000 shipments: Canada Post leads at 75.59% on-time "
            "(avg delay 2.50h, avg cost CAD $74.43), tied with UPS (75.59%, 2.50h, $74.26). "
            "DHL ranks third at 75.44% (2.44h, $74.37) with the lowest average delay. "
            "Purolator sits at 75.22% (2.56h, $74.32), while FedEx trails at 74.96% (2.59h, $74.06). "
            "The performance spread is only 0.63 percentage points — indicating systemic network-wide "
            "factors rather than carrier-specific failures. "
            "Cost differences are negligible (~$0.37 range across all carriers). "
            "Recommendation: enforce unified SLA for all five carriers and target 80% on-time by Q2 end."
        )

    # ── Delay analysis ────────────────────────────────────────────────────────
    if any(w in u for w in ["delay", "late", "bottleneck", "slow"]):
        return (
            "Delay analysis across the Propgatics dataset shows 24.74% of all shipments delayed, "
            "with an average delay of 2.52 hours. Critical Delay (>4h) affects ~2% of total volume. "
            "Weather is the single largest delay driver: Storm and Snow conditions add an average of "
            "4.1 extra hours versus Clear-weather routes. Rain adds approximately 1.8 hours. "
            "High-traffic corridors amplify weather delays significantly. "
            "Worst corridors by average delay: Vancouver-bound long-haul routes (mountain pass exposure), "
            "Halifax–Montreal (Atlantic weather), and Edmonton–Kelowna (winter roads). "
            "Deploy buffer capacity and pre-emptive rerouting on these corridors to reduce Critical Delays by an estimated 15–20%."
        )

    # ── Route analysis ────────────────────────────────────────────────────────
    if any(w in u for w in ["route", "popular", "busiest", "corridor", "top route", "best route", "worst route"]):
        return (
            "Route analysis shows the Calgary–Edmonton corridor is the busiest by volume (~300km, highest on-time). "
            "Toronto–Montreal and Toronto–Vancouver are the highest-revenue routes. "
            "Delay rates are highest on long-haul routes involving Vancouver as destination, "
            "driven by mountain pass weather exposure (31% delay rate in Feb snow events). "
            "Short-haul routes within the Prairie provinces show the best on-time performance (78–80%). "
            "Halifax–Montreal carries an Atlantic weather risk rating with a 27% delay rate. "
            "Prioritise capacity on Toronto–Vancouver and Toronto–Montreal for maximum revenue impact."
        )

    # ── Trend / time analysis ─────────────────────────────────────────────────
    if any(w in u for w in ["trend", "week", "month", "quarterly", "seasonal", "over time",
                              "year over year", "time series", "growth", "history", "historical"]):
        return (
            "Monthly shipment volume is stable with ±6% variance. "
            "Delay rates show a seasonal peak in February–March coinciding with winter storms across "
            "Prairie and Atlantic provinces. On-time delivery improved ~3 percentage points "
            "between January and March 2026, suggesting positive effects from mid-quarter operational changes. "
            "Q1 2026 total: 24,823 shipments, 75.3% on-time, CAD $1.84M revenue. "
            "Incident rates closely track delay rates with a ~48-hour lag (consistent with post-resolution reporting). "
            "Q2 projection: on-time rate should reach 77–78% if weather-aware routing is deployed in April."
        )

    # ── Incident analysis ─────────────────────────────────────────────────────
    if any(w in u for w in ["incident", "damage", "lost", "customs", "failed delivery"]):
        return (
            "Incident analysis across 25,000 records: Failed Delivery Attempt is most common at 28%, "
            "followed by Damaged Shipment (22%), Customs Hold (18%), Weather Delay (15%), "
            "Lost Package (10%), Mechanical Failure (5%), and Address Error (2%). "
            "Critical severity: ~10% of incidents, avg financial loss CAD $2,800, avg resolution 96h. "
            "High severity: ~15%, avg loss $2,200, 84h resolution. "
            "Medium: 34%, avg loss $1,500, 60h. Low: 41%, avg loss $800, 36h. "
            "Status breakdown: 65% Resolved, 25% Under Investigation, 10% Open. "
            "Mean resolution time across all severity levels: 68h. "
            "Action: escalation protocols needed for Critical incidents to cut resolution time below 72h."
        )

    # ── Risk analysis ─────────────────────────────────────────────────────────
    if any(w in u for w in ["risk", "risk score", "risk profile", "risk distribution"]):
        return (
            "Route risk analysis shows a mean risk score of 16.3 out of 100 across all shipments. "
            "~8% of shipments are classified High or Critical risk. "
            "Risk correlates strongly with distance, traffic level, and adverse weather. "
            "Vancouver-bound routes carry the highest composite risk scores due to mountain pass exposure. "
            "Halifax–Montreal and Edmonton–Kelowna corridors are the next riskiest. "
            "Implementing pre-emptive rerouting for High-risk shipments during storm windows "
            "could reduce Critical Delay incidents by an estimated 15–20%. "
            "Low-risk shipments (score <20) represent 67% of total volume and run a 79% on-time rate."
        )

    # ── Weather impact ────────────────────────────────────────────────────────
    if any(w in u for w in ["weather", "storm", "snow", "rain", "fog", "cloudy"]):
        return (
            "Weather impact analysis: Storm conditions add an average of 4.1 extra hours of delay "
            "vs Clear-weather routes. Snow adds ~3.2h, Fog ~1.9h, Rain ~1.8h, Cloudy ~0.6h. "
            "Storm-affected routes see a 35% higher incident rate than Clear routes. "
            "Atlantic Canada and mountain pass corridors are most weather-exposed. "
            "Weather is the primary delay driver, accounting for ~42% of all delays in Q1 2026. "
            "Recommendation: integrate a weather-based dynamic buffer into EDD calculations — "
            "a +2h Storm buffer and +1h Snow buffer would bring estimated on-time rates to ~79%."
        )

    # ── Financial / cost / revenue analysis ───────────────────────────────────
    if any(w in u for w in ["financial", "revenue", "cost", "profitability", "roi",
                              "spend", "expenditure", "shipping spend", "cost efficiency"]):
        return (
            "Financial analysis of the Propgatics network: total shipping revenue is CAD $7.43M "
            "(avg $74.30 per shipment) against delivery cost of CAD $18.86M (avg $188.60 per shipment). "
            "The cost-to-revenue ratio stands at 2.5× — a structural deficit requiring a pricing review. "
            "FedEx has the lowest avg shipping cost ($74.06) and lowest on-time rate; "
            "Canada Post has the highest cost ($74.43) and highest on-time rate. "
            "Total incident financial losses: estimated at CAD $17.5M across 25,000 incidents. "
            "Top revenue corridors: Toronto–Vancouver and Toronto–Montreal. "
            "Recommended action: raise freight rates by 15–20% and renegotiate carrier contracts to "
            "shift a portion of delivery costs back to carriers under performance SLAs."
        )

    # ── Cancellation / critical delays ───────────────────────────────────────
    if any(w in u for w in ["cancel", "cancellation", "critical delay"]):
        return (
            "Cancellation rate is sub-1% across the Propgatics dataset — within normal operational thresholds. "
            "Critical Delay (the most severe status short of cancellation) affects ~1.9% of shipments. "
            "Critical Delays are most concentrated in Vancouver-bound long-haul and Halifax routes. "
            "The primary drivers are customer-requested holds and customs documentation issues. "
            "No single carrier is disproportionately responsible. "
            "Monitor closely if Critical Delay rates rise above 3% — that is a leading indicator of "
            "systemic carrier or routing failures."
        )

    # ── Carrier ranking ───────────────────────────────────────────────────────
    if any(w in u for w in ["ranking", "ranked", "top carrier", "best carrier", "worst carrier"]):
        return (
            "Carrier ranking by on-time delivery (100K shipments): "
            "1st Canada Post 75.59% (avg delay 2.50h) · "
            "1st UPS 75.59% (2.50h) · "
            "3rd DHL 75.44% (2.44h — lowest delay hours) · "
            "4th Purolator 75.22% (2.56h) · "
            "5th FedEx 74.96% (2.59h — highest delay hours). "
            "Average cost ranking (cheapest to most expensive): "
            "FedEx $74.06 · UPS $74.26 · DHL $74.37 · Purolator $74.32 · Canada Post $74.43. "
            "Overall value score (on-time rate / cost): DHL leads due to low delay + moderate cost."
        )

    return (
        "Propgatics operations summary: 100,000 shipments processed across 5 Canadian carriers "
        "(UPS, FedEx, DHL, Canada Post, Purolator). "
        "On-time delivery rate: 75.26%. Average delay: 2.52 hours. "
        "Total shipping revenue: CAD $7.43M. Incident count: 25,000 across 7+ incident types. "
        "Key risk areas: long-haul routes in adverse weather, particularly Vancouver-bound corridors. "
        "Recommend carrier SLA review and weather-aware dynamic routing for Q3."
    )


def _mock_conversation(user: str) -> str:
    u = user.lower()

    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "howdy", "sup"]
    if any(g in u for g in greetings):
        return random.choice([
            "Hello! I'm the Propgatics GenAI Operations Assistant — a 4-agent AI system connected to "
            "the Propgatics Logistics Intelligence Platform. I can help you with:\n\n"
            "• **Shipment data** — query 5,000 seeded shipments across UPS, FedEx, DHL, Canada Post, Purolator\n"
            "• **Incident intelligence** — 1,000 incident records with severity, financial loss, resolution time\n"
            "• **Analytics & KPIs** — on-time rates, delay trends, carrier benchmarks, risk scores\n"
            "• **Document knowledge** — platform methodology, carrier reports, HR policies\n\n"
            "Try: *\"Show delayed FedEx shipments\"*, *\"Which carrier has the worst on-time rate?\"*, "
            "or *\"What's our overall KPI summary?\"*",

            "Hi! I'm your AI logistics co-pilot backed by 100K shipments of Propgatics data. "
            "Ask me to pull shipment records, run carrier performance analysis, compare routes, "
            "or explain the platform. What would you like to explore?",
        ])

    if any(w in u for w in ["bye", "goodbye", "see you", "exit", "quit"]):
        return "Goodbye! The Propgatics platform stays live — come back anytime to dive into the data."

    if any(w in u for w in ["what can you do", "capabilities", "help", "how do you work", "what are you"]):
        return (
            "I'm a multi-agent AI assistant connected to the Propgatics Logistics Intelligence Platform:\n\n"
            "**1. SQL Agent** — queries the live shipments & incidents database\n"
            "   → *\"Show Critical Delay shipments from Calgary\"*\n"
            "   → *\"How many incidents did FedEx have?\"*\n\n"
            "**2. Analytics Agent** — computes KPIs, trends, carrier benchmarks, risk analysis\n"
            "   → *\"Compare carrier on-time rates\"*\n"
            "   → *\"What's the weather impact on delays?\"*\n\n"
            "**3. Knowledge Agent** — answers questions from platform docs and uploaded files\n"
            "   → *\"How was the Propgatics dataset generated?\"*\n"
            "   → *\"What's the HR leave policy?\"*\n\n"
            "**4. Conversation Agent** — that's me. I handle everything else.\n\n"
            "Your questions are automatically routed to the right agent."
        )

    if any(w in u for w in ["thank", "thanks", "great", "awesome", "nice", "good job", "perfect"]):
        return random.choice([
            "You're welcome! Let me know if there's anything else you'd like to analyze.",
            "Happy to help! Feel free to dig deeper into any carrier, route, or incident category.",
            "Glad that was useful! What else would you like to explore in the Propgatics data?",
        ])

    if any(w in u for w in ["who built", "who made", "who created", "what is this"]):
        return (
            "This is the **Propgatics GenAI Operations Assistant** — a production-grade multi-agent "
            "AI system integrated with the **Propgatics Logistics Intelligence Platform**.\n\n"
            "The platform covers 100K shipments, 25K incidents, 5 Canadian carriers, and real route "
            "risk intelligence. The GenAI layer is built with FastAPI and React: "
            "a Router agent dispatches natural-language questions to specialised SQL, Analytics, "
            "Knowledge, and Conversation agents. It supports pluggable LLM providers "
            "(Groq, OpenAI, Anthropic, or mock mode)."
        )

    if any(w in u for w in ["how are you", "how's it going", "how are things"]):
        return "Running at full capacity and ready to analyze your logistics data! What can I help with?"

    if "?" not in u and len(u.split()) <= 3:
        return (
            f"Received: *\"{user}\"*. Could you be more specific? "
            "Try: *\"Show delayed shipments\"*, *\"KPI summary\"*, or *\"Which routes have the highest risk?\"* "
            "Type *\"help\"* to see everything I can do."
        )

    return (
        "Let me make sure I give you the most accurate answer. Could you clarify?\n\n"
        "Things I can help with:\n"
        "• **Shipment queries**: *\"Show UPS shipments to Vancouver this month\"*\n"
        "• **Incident analysis**: *\"List unresolved Critical incidents\"*\n"
        "• **Analytics**: *\"What's the delay trend by weather condition?\"*\n"
        "• **Reports**: *\"Give me a full KPI summary\"*"
    )


def _mock_knowledge(user: str) -> str:
    u = user.lower()

    # ── Propgatics platform knowledge ──────────────────────────────────────────
    if any(w in u for w in ["propgatics", "platform", "how was", "dataset", "generated",
                              "what is propgatics", "about propgatics"]):
        return (
            "Propgatics is an end-to-end logistics and shipment analytics platform simulating a "
            "real-world operational intelligence system. The dataset was generated synthetically "
            "using OpenRouteService (ORS) API for real Canadian route distances and durations, "
            "with shipment attributes (carrier, weather, traffic, incidents) added via controlled "
            "randomisation to reflect realistic logistics distributions. "
            "The full dataset includes 100,000 shipment records and 25,000 incident records "
            "across 5 carriers serving major Canadian cities."
        )
    if any(w in u for w in ["ors", "openrouteservice", "routing api", "route calculation"]):
        return (
            "OpenRouteService (ORS) is an open-source routing engine used by Propgatics to compute "
            "real driving distances and estimated durations between Canadian city pairs. "
            "The API was accessed with an authentication key passed in the request header. "
            "Route data (distance_km, estimated_duration_hours) in the shipments dataset comes "
            "directly from ORS responses, making the logistics simulation geographically accurate."
        )

    # ── KPI / performance knowledge ────────────────────────────────────────────
    if any(w in u for w in ["on-time", "on time", "delivery rate", "kpi", "overall performance"]):
        return (
            "Propgatics platform KPIs (full 100K dataset): "
            "**On-time delivery rate: 75.26%**. Delayed rate: 24.74%. "
            "Average delay: 2.52 hours. Total shipping revenue: CAD $7,430,259. "
            "Total delivery cost: CAD $18,860,452. Average route risk score: 16.32/100. "
            "Total incidents recorded: 25,000."
        )
    if "carrier" in u:
        return (
            "Carrier performance (full 100K dataset): "
            "Canada Post 75.59% on-time (avg delay 2.50h, avg cost $74.43). "
            "UPS 75.59% (2.50h, $74.26). DHL 75.44% (2.44h, $74.37). "
            "Purolator 75.22% (2.56h, $74.32). FedEx 74.96% (2.59h, $74.06). "
            "All carriers within 0.63pp of each other — systemic issues dominate."
        )

    # ── HR / Leave policy ──────────────────────────────────────────────────────
    if any(w in u for w in ["annual leave", "vacation", "time off", "pto"]):
        return (
            "Annual Leave Policy: Full-time employees accrue 20 days per calendar year, "
            "credited quarterly (5 days/quarter). Up to 5 unused days carry over; remainder "
            "forfeited December 31st. Leave cannot be taken in the first 90 days of employment. "
            "Submit requests via HR portal at least 5 business days in advance "
            "(10 business days in Q4 peak Oct–Dec)."
        )
    if any(w in u for w in ["sick", "sick leave", "medical leave"]):
        return (
            "Sick Leave Policy: 10 paid sick days per year, no carryover. "
            "Medical certificate required for sick leave exceeding 3 consecutive days. "
            "Exhausted sick leave may be followed by up to 30 days unpaid medical leave with HR approval."
        )
    if any(w in u for w in ["parental", "maternity", "paternity"]):
        return (
            "Parental Leave: Primary caregivers receive 16 weeks paid leave. "
            "Secondary caregivers receive 4 weeks. Must commence within 12 months of birth or adoption."
        )
    if any(w in u for w in ["bereavement", "compassionate"]):
        return (
            "Bereavement Leave: 5 paid days for immediate family (spouse, child, parent, sibling). "
            "2 paid days for extended family."
        )
    if any(w in u for w in ["remote", "wfh", "work from home", "hybrid"]):
        return (
            "Remote Work Policy: Up to 3 days/week with manager approval. "
            "Full remote requires VP approval, reviewed quarterly. "
            "Core hours: 10am–3pm local time."
        )
    if any(w in u for w in ["performance review", "appraisal", "review cycle"]):
        return (
            "Performance Reviews: Conducted bi-annually in June and December. "
            "Compensation adjustments tied to year-end review. "
            "2 weeks notice required before the review date."
        )
    if any(w in u for w in ["policy", "leave", "hr", "handbook", "entitlement"]):
        return (
            "Propgatics HR Policies (Effective January 2026): "
            "Annual Leave: 20 days/year (5 days carry-over max). "
            "Sick Leave: 10 days/year (no carry-over). "
            "Parental Leave: 16 weeks primary / 4 weeks secondary. "
            "Bereavement: 5 days immediate family / 2 days extended. "
            "Remote Work: up to 3 days/week with manager approval. "
            "Reviews: bi-annual (June + December)."
        )

    # ── Q1 report knowledge ────────────────────────────────────────────────────
    if any(w in u for w in ["q1", "q1 report", "q1 2026", "first quarter"]):
        return (
            "Q1 2026 Operations Report Summary: 24,823 shipments, 75.3% on-time, "
            "CAD $1.84M revenue, $4.68M delivery cost (2.5× ratio). "
            "Best route: Calgary–Edmonton (78.4% on-time). "
            "Worst: Vancouver-bound long-haul (31% delay rate in Feb snow events). "
            "6,203 incidents in Q1. Top types: Failed Delivery Attempt (28%), Damaged Shipment (22%). "
            "Q2 targets: 80%+ on-time, weather-aware routing, FedEx SLA renegotiation."
        )

    return (
        "I can answer questions about the Propgatics platform, HR policies, and operational reports. "
        "Try: *\"What's our on-time delivery rate?\"*, *\"Tell me about the HR leave policy\"*, "
        "or *\"Summarise Q1 2026 operations.\"*"
    )
