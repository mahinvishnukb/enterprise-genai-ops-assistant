"""
LLMClient: single seam between app logic and the model vendor.

Switch provider via LLM_PROVIDER env var:
  mock      — rich deterministic responses, no API key, used in CI and free deployments
  openai    — GPT-4o-mini via OpenAI SDK
  anthropic — Claude 3.5 Sonnet via Anthropic SDK

Mock responses reflect the Propgatics Logistics Intelligence Platform dataset:
  100K shipments across 5 Canadian carriers (UPS, FedEx, DHL, Canada Post, Purolator)
  25K incidents, 75.26% on-time delivery, 24.74% delayed.
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
    """Returns a 3-line string:
    line 1 = best agent name
    line 2 = confidence (0.0–1.0)
    line 3 = second-best agent or 'none'
    Confidence is proportional to how decisively one category's keywords won."""
    u = user.lower()

    pure_chat = ["hi", "hello", "hey", "good morning", "good afternoon",
                 "what's up", "howdy", "sup", "greetings", "how are you",
                 "thank you", "thanks", "great job", "who are you",
                 "what are you", "what can you do", "who built you",
                 "capabilities", "how do you work", "tell me about yourself"]
    pure_chat_hit = any(u == g or u.startswith(g + " ") or u.startswith(g + "!") for g in pure_chat)

    # Document / knowledge signals — platform docs, policies, methodology
    doc_signals = [
        "policy", "entitlement", "sick leave", "annual leave", "vacation",
        "parental", "maternity", "paternity", "bereavement", "remote work",
        "wfh", "onboard", "performance review", "appraisal", "hr ",
        "handbook", "sop", "procedure", "regulation", "compliance",
        "according to", "what does the document", "leave policy",
        "propgatics", "platform", "ors", "openrouteservice",
        "how was the data", "methodology", "how does it work",
        "carrier performance report", "q1 report", "q2 report",
        "port congestion", "sla", "northroute", "fastfreight", "pacificlink",
    ]

    # Analytics signals — computed insights, not raw rows
    analytics_signals = [
        "trend", "kpi", "summary", "overview", "insight",
        "anomaly", "over time", "weekly", "monthly", "performance",
        "dashboard", "hotspot", "busiest", "worst route", "best route",
        "most delay", "highest delay", "most delays", "which route",
        "rate", "percentage", "average delay", "analysis", "report",
        "breakdown", "distribution", "compare", "comparison",
        "carrier performance", "on-time rate", "risk score",
        "weather impact", "financial loss", "incident rate",
    ]

    # SQL signals — show/list/find raw rows
    data_words = [
        "shipment", "delay", "cancel", "origin", "destination",
        "tracking", "carrier", "route", "status", "toronto", "vancouver",
        "calgary", "montreal", "edmonton", "halifax", "moncton", "ottawa",
        "ups", "fedex", "dhl", "purolator",
        "show", "list", "find", "fetch", "display", "count", "how many",
        "get all", "all delayed", "all cancelled", "recent", "latest",
        "last month", "last week", "incident", "warehouse", "driver",
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
    """Generate deterministic SQL against the shipments / incidents schema."""
    u = user.lower()
    cities = [
        "toronto", "vancouver", "calgary", "montreal", "edmonton",
        "halifax", "moncton", "ottawa", "kelowna", "winnipeg",
    ]
    carriers = ["ups", "fedex", "dhl", "canada post", "purolator"]

    # ── Incident queries ───────────────────────────────────────────────────
    if "incident" in u:
        if "critical" in u:
            return "SELECT incident_id, carrier, origin, destination, incident_type, estimated_financial_loss_cad FROM incidents WHERE severity_level = 'Critical' ORDER BY estimated_financial_loss_cad DESC LIMIT 20;"
        if "unresolved" in u or "open" in u or "investigation" in u:
            return "SELECT incident_id, carrier, incident_type, severity_level, incident_status, delay_hours FROM incidents WHERE incident_status != 'Resolved' ORDER BY delay_hours DESC LIMIT 20;"
        if "financial" in u or "loss" in u or "cost" in u:
            return "SELECT carrier, COUNT(*) as incidents, ROUND(SUM(estimated_financial_loss_cad),2) as total_loss_cad FROM incidents GROUP BY carrier ORDER BY total_loss_cad DESC;"
        return "SELECT incident_id, carrier, origin, destination, incident_type, severity_level, incident_status, delay_hours FROM incidents ORDER BY delay_hours DESC LIMIT 30;"

    # ── Count / aggregate queries ──────────────────────────────────────────
    if "how many" in u or ("count" in u and "group" not in u):
        if "delayed" in u or "delay" in u:
            return "SELECT COUNT(*) as delayed_count FROM shipments WHERE shipment_status IN ('Delayed', 'Minor Delay', 'Critical Delay');"
        if "cancel" in u:
            return "SELECT COUNT(*) as cancelled_count FROM shipments WHERE shipment_status = 'Cancelled';"
        for city in cities:
            if city in u:
                cap = city.title()
                return f"SELECT COUNT(*) as count FROM shipments WHERE destination = '{cap}' OR origin = '{cap}';"
        return "SELECT shipment_status, COUNT(*) as count FROM shipments GROUP BY shipment_status ORDER BY count DESC;"

    # ── Carrier queries ────────────────────────────────────────────────────
    for carrier in carriers:
        if carrier in u:
            cap = carrier.title()
            if "delay" in u or "late" in u:
                return f"SELECT shipment_id, origin, destination, shipment_status, delay_hours, shipment_date FROM shipments WHERE carrier = '{cap}' AND shipment_status IN ('Delayed','Minor Delay','Critical Delay') ORDER BY delay_hours DESC LIMIT 30;"
            if "performance" in u or "on-time" in u or "on time" in u:
                return f"SELECT carrier, COUNT(*) as total, SUM(on_time_delivery) as on_time, ROUND(AVG(on_time_delivery)*100,1) as on_time_pct, ROUND(AVG(delay_hours),2) as avg_delay_hours FROM shipments WHERE carrier = '{cap}' GROUP BY carrier;"
            return f"SELECT shipment_id, origin, destination, shipment_status, delay_hours, shipping_cost_cad, shipment_date FROM shipments WHERE carrier = '{cap}' ORDER BY shipment_date DESC LIMIT 30;"

    # ── Risk / weather / traffic ───────────────────────────────────────────
    if "risk" in u or "high risk" in u or "critical" in u:
        return "SELECT shipment_id, carrier, origin, destination, route_risk_score, risk_category, shipment_status FROM shipments WHERE risk_category IN ('High','Critical') ORDER BY route_risk_score DESC LIMIT 30;"
    if "weather" in u:
        return "SELECT weather_condition, COUNT(*) as shipments, SUM(CASE WHEN shipment_status IN ('Delayed','Minor Delay','Critical Delay') THEN 1 ELSE 0 END) as delays, ROUND(AVG(delay_hours),2) as avg_delay FROM shipments GROUP BY weather_condition ORDER BY delays DESC;"
    if "traffic" in u:
        return "SELECT traffic_level, COUNT(*) as shipments, ROUND(AVG(delay_hours),2) as avg_delay_hours FROM shipments GROUP BY traffic_level ORDER BY avg_delay_hours DESC;"

    # ── Worst / best routes ────────────────────────────────────────────────
    if "worst" in u or "most delay" in u or "highest delay" in u:
        return "SELECT origin, destination, COUNT(*) as total, SUM(CASE WHEN shipment_status IN ('Delayed','Minor Delay','Critical Delay') THEN 1 ELSE 0 END) as delays, ROUND(AVG(delay_hours),2) as avg_delay_hours FROM shipments GROUP BY origin, destination HAVING delays > 0 ORDER BY avg_delay_hours DESC LIMIT 10;"
    if "best" in u or "fastest" in u or "on-time" in u or "on time" in u:
        return "SELECT carrier, ROUND(AVG(on_time_delivery)*100,1) as on_time_pct, ROUND(AVG(delay_hours),2) as avg_delay_hours FROM shipments GROUP BY carrier ORDER BY on_time_pct DESC;"

    # ── Delayed shipments ──────────────────────────────────────────────────
    if "delayed" in u or "delay" in u or "late" in u:
        for city in cities:
            if city in u:
                cap = city.title()
                return f"SELECT shipment_id, carrier, origin, destination, shipment_status, delay_hours, delay_reason, shipment_date FROM shipments WHERE shipment_status IN ('Delayed','Minor Delay','Critical Delay') AND (origin='{cap}' OR destination='{cap}') ORDER BY delay_hours DESC LIMIT 30;"
        return "SELECT shipment_id, carrier, origin, destination, shipment_status, delay_hours, delay_reason, shipment_date FROM shipments WHERE shipment_status IN ('Delayed','Minor Delay','Critical Delay') ORDER BY delay_hours DESC LIMIT 50;"

    # ── City-specific queries ──────────────────────────────────────────────
    for city in cities:
        if city in u:
            cap = city.title()
            if "from" in u:
                direction = f"WHERE origin = '{cap}'"
            elif "to" in u:
                direction = f"WHERE destination = '{cap}'"
            else:
                direction = f"WHERE origin = '{cap}' OR destination = '{cap}'"
            return f"SELECT shipment_id, carrier, origin, destination, shipment_status, delay_hours, shipment_date FROM shipments {direction} ORDER BY shipment_date DESC LIMIT 30;"

    # ── Route summary ──────────────────────────────────────────────────────
    if "route" in u:
        return "SELECT origin, destination, COUNT(*) as shipments, ROUND(AVG(delay_hours),2) as avg_delay, ROUND(AVG(on_time_delivery)*100,1) as on_time_pct FROM shipments GROUP BY origin, destination ORDER BY shipments DESC LIMIT 15;"

    # ── Carrier breakdown ──────────────────────────────────────────────────
    if "carrier" in u or "by carrier" in u:
        return "SELECT carrier, COUNT(*) as total_shipments, ROUND(AVG(on_time_delivery)*100,1) as on_time_pct, ROUND(AVG(delay_hours),2) as avg_delay_hours, ROUND(AVG(shipping_cost_cad),2) as avg_cost_cad FROM shipments GROUP BY carrier ORDER BY on_time_pct DESC;"

    # ── Recent / latest / default ──────────────────────────────────────────
    if "recent" in u or "latest" in u or "last" in u:
        return "SELECT shipment_id, carrier, origin, destination, shipment_status, delay_hours, shipment_date FROM shipments ORDER BY shipment_date DESC LIMIT 20;"

    return "SELECT shipment_id, carrier, origin, destination, shipment_status, delay_hours, shipping_cost_cad, shipment_date FROM shipments ORDER BY shipment_date DESC LIMIT 20;"


def _mock_report(user: str) -> str:
    """Narrate analytics findings using real Propgatics platform numbers."""
    u = user.lower()

    if "kpi" in u or "summary" in u or "overview" in u or "dashboard" in u:
        return (
            "The Propgatics platform is tracking 100,000 shipments across five major Canadian carriers. "
            "Overall on-time delivery stands at 75.26%, with 24.74% of shipments experiencing some form "
            "of delay — above the industry benchmark of 15%, signalling a need for carrier SLA review. "
            "Average delay duration is 2.52 hours across affected shipments. "
            "FedEx has the lowest on-time rate at 74.96%, while Canada Post leads at 75.59% — "
            "a narrow spread suggesting systemic rather than carrier-specific issues. "
            "Total shipping revenue is CAD $7.43M against delivery costs of CAD $18.86M; "
            "close attention to route profitability is recommended."
        )
    if "carrier" in u or "performance" in u:
        return (
            "Carrier performance analysis across 100,000 shipments shows FedEx as the lowest performer "
            "at 74.96% on-time, followed by Purolator (75.22%), DHL (75.44%), UPS (75.59%), "
            "and Canada Post leading at 75.59%. "
            "Average delay hours are tightest for DHL at 2.44 h and widest for FedEx at 2.59 h. "
            "Average shipping costs are consistent across all carriers at approximately CAD $74. "
            "Given the narrow performance band, contract renegotiation and SLA enforcement are recommended "
            "for all carriers rather than singling out one vendor."
        )
    if "delay" in u or "late" in u or "bottleneck" in u:
        return (
            "Delay analysis across the shipment dataset shows 24.74% of shipments delayed, "
            "with an average delay of 2.52 hours. "
            "Critical delays (> threshold) affect approximately 2% of total volume. "
            "Weather is the single largest delay driver, particularly Snow and Storm conditions, "
            "which correlate with a 40% higher average delay versus Clear-weather shipments. "
            "High-traffic routes compound weather impact significantly. "
            "Routes between major hubs (Toronto–Vancouver, Calgary–Montreal) show the highest absolute "
            "delay volumes due to shipment density — recommend deploying buffer capacity on these corridors."
        )
    if "route" in u or "popular" in u or "busiest" in u:
        return (
            "Route analysis shows the Calgary–Edmonton corridor is the busiest single route by volume, "
            "owing to its short distance (300 km) and high business customer density. "
            "Toronto–Montreal and Toronto–Vancouver are the highest-revenue routes. "
            "Delay rates are highest on long-haul routes involving Vancouver as destination, "
            "likely influenced by weather exposure over mountain passes. "
            "Short-haul routes within the Prairie provinces show the best on-time performance. "
            "Recommend prioritising capacity on Toronto–Vancouver and Toronto–Montreal for maximum revenue impact."
        )
    if "trend" in u or "week" in u or "month" in u or "over time" in u:
        return (
            "Weekly shipment volume is stable with ±6% variance week-over-week. "
            "Delay rates show a seasonal pattern, peaking in February and March — coinciding with "
            "winter storm events across Prairie and Atlantic provinces. "
            "On-time delivery improved by approximately 3 percentage points between January and March 2026, "
            "suggesting positive effects from operational adjustments mid-quarter. "
            "Incident rates track closely with delay rates, with a lag of roughly 48 hours, "
            "consistent with incident reports being filed after resolution attempts."
        )
    if "incident" in u:
        return (
            "Incident analysis across 25,000 records shows Failed Delivery Attempt as the most common "
            "incident type (~28%), followed by Damaged Shipment (22%) and Customs Hold (18%). "
            "Critical-severity incidents account for approximately 10% of all incidents and carry "
            "an average financial loss of CAD $2,800 per event. "
            "DHL and FedEx have the highest incident-to-shipment ratios. "
            "Mean resolution time is 68 hours across all severity levels; "
            "Critical incidents average 96 hours, suggesting a need for escalation protocols."
        )
    if "risk" in u:
        return (
            "Route risk analysis shows a mean risk score of 16.3 out of 100 across all shipments, "
            "with approximately 8% classified as High or Critical risk. "
            "Risk correlates strongly with distance, traffic level, and adverse weather conditions. "
            "The Vancouver-bound routes carry the highest composite risk scores. "
            "Implementing pre-emptive rerouting for High-risk shipments during storm windows "
            "could reduce Critical Delay incidents by an estimated 15-20%."
        )
    if "weather" in u:
        return (
            "Weather impact analysis shows Storm and Snow conditions add an average of 4.1 extra hours "
            "of delay versus Clear conditions. Rain adds approximately 1.8 hours on average. "
            "Snow-affected routes see a 35% higher incident rate than Clear routes. "
            "Atlantic Canada and mountain pass routes are most exposed to adverse weather. "
            "Recommend integrating a weather-based dynamic buffer into estimated delivery date calculations."
        )
    if "cancel" in u:
        return (
            "Cancellation analysis shows a sub-1% cancellation rate across the Propgatics dataset, "
            "which is well within normal operational thresholds. "
            "The primary drivers are customer-requested holds and customs documentation issues. "
            "No single carrier or route is disproportionately responsible. "
            "Monitor if cancellation rates rise above 2% as a leading indicator of systemic issues."
        )
    return (
        "Propgatics operations summary: 100,000 shipments processed across 5 Canadian carriers "
        "(UPS, FedEx, DHL, Canada Post, Purolator). "
        "On-time delivery rate: 75.26%. Average delay: 2.52 hours. "
        "Total shipping revenue: CAD $7.43M. Incident count: 25,000 across 19 incident types. "
        "Key risk areas: long-haul routes in adverse weather, particularly Vancouver-bound corridors. "
        "Recommend carrier SLA review and weather-aware dynamic routing for Q3."
    )


def _mock_conversation(user: str) -> str:
    u = user.lower()

    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "howdy"]
    if any(g in u for g in greetings):
        return random.choice([
            "Hello! I'm the Propgatics GenAI Operations Assistant — a 4-agent AI system connected to "
            "the Propgatics Logistics Intelligence Platform. I can help you with:\n\n"
            "• **Shipment data** — query 5,000 real shipments across UPS, FedEx, DHL, Canada Post, Purolator\n"
            "• **Incident intelligence** — 1,000 incident records with severity, financial loss, resolution time\n"
            "• **Analytics & KPIs** — on-time rates, delay trends, carrier benchmarks, risk scores\n"
            "• **Document knowledge** — platform methodology, carrier reports, HR policies\n\n"
            "Try: *\"Show delayed FedEx shipments\"*, *\"Which carrier has the worst on-time rate?\"*, "
            "or *\"What's our overall KPI summary?\"*",

            "Hi! I'm your AI logistics co-pilot backed by 100K shipments of Propgatics data. "
            "Ask me to pull shipment records, run carrier performance analysis, or explain the platform. "
            "What would you like to explore?",
        ])

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

    if any(w in u for w in ["who built", "who made", "who created", "what is this", "propgatics"]):
        return (
            "This is the **Propgatics GenAI Operations Assistant** — a production-grade multi-agent "
            "AI system integrated with the **Propgatics Logistics Intelligence Platform** — an end-to-end logistics analytics "
            "system covering 100K shipments, 25K incidents, 5 Canadian carriers, and real route "
            "risk intelligence.\n\n"
            "The GenAI layer is a production-grade multi-agent system built with FastAPI and React: "
            "a Router agent dispatches natural-language questions to specialized SQL, Analytics, "
            "Knowledge, and Conversation agents. It supports pluggable LLM providers "
            "(OpenAI, Anthropic, or mock mode for offline use)."
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

    # ── Propgatics platform knowledge ──────────────────────────────────────
    if "propgatics" in u or "platform" in u or "how was" in u or "dataset" in u or "generated" in u:
        return (
            "Propgatics is an end-to-end logistics and shipment analytics platform simulating a "
            "real-world operational intelligence system. The dataset was generated synthetically "
            "using OpenRouteService (ORS) API for real Canadian route distances and durations, "
            "with shipment attributes (carrier, weather, traffic, incidents) added via controlled "
            "randomisation to reflect realistic logistics distributions. "
            "The full dataset includes 100,000 shipment records and 25,000 incident records "
            "across 5 carriers serving major Canadian cities."
        )
    if "ors" in u or "openrouteservice" in u or "api" in u:
        return (
            "OpenRouteService (ORS) is an open-source routing engine used by Propgatics to compute "
            "real driving distances and estimated durations between Canadian city pairs. "
            "The API was accessed with an authentication key passed in the request header. "
            "Route data (distance_km, estimated_duration_hours) in the shipments dataset comes "
            "directly from ORS responses, making the logistics simulation geographically accurate."
        )

    # ── KPI / performance knowledge ────────────────────────────────────────
    if "on-time" in u or "on time" in u or "delivery rate" in u or "kpi" in u:
        return (
            "Propgatics platform KPIs (full 100K dataset): "
            "**On-time delivery rate: 75.26%**. Delayed rate: 24.74%. "
            "Average delay: 2.52 hours. Total shipping revenue: CAD $7,430,259. "
            "Total delivery cost: CAD $18,860,452. Average route risk score: 16.32/100. "
            "Total incidents recorded: 25,000."
        )
    if "carrier" in u:
        return (
            "Carrier performance across 100,000 shipments:\n"
            "• **Canada Post** — 75.59% on-time, avg delay 2.50 h, avg cost CAD $74.43\n"
            "• **UPS** — 75.59% on-time, avg delay 2.50 h, avg cost CAD $74.26\n"
            "• **DHL** — 75.44% on-time, avg delay 2.44 h, avg cost CAD $74.37\n"
            "• **Purolator** — 75.22% on-time, avg delay 2.56 h, avg cost CAD $74.32\n"
            "• **FedEx** — 74.96% on-time, avg delay 2.59 h, avg cost CAD $74.06\n"
            "All carriers perform within a 0.6 percentage-point band, suggesting systemic issues "
            "rather than carrier-specific failures."
        )
    if "incident" in u and ("type" in u or "kind" in u or "what" in u):
        return (
            "Incident types in the Propgatics dataset include: Failed Delivery Attempt, "
            "Damaged Shipment, Lost Package, Customs Hold, Weather Delay, Mechanical Failure, "
            "and Address Error. Severity levels range from Low to Critical. "
            "Incident status can be Resolved, Under Investigation, or Open. "
            "Average financial loss per incident: approximately CAD $1,800; "
            "Critical incidents average CAD $2,800."
        )
    if "risk" in u and ("category" in u or "score" in u or "what" in u):
        return (
            "Route risk scores in Propgatics are composite scores (0–100) computed from distance, "
            "weather exposure, traffic levels, and historical delay patterns. "
            "Risk categories: Low (score < 20), Medium (20–40), High (40–60), Critical (> 60). "
            "Mean score across the full dataset is 16.32, indicating most routes are Low risk. "
            "Approximately 8% of shipments fall into High or Critical risk categories."
        )

    # ── HR policy answers ──────────────────────────────────────────────────
    if "sick" in u:
        return "Employees receive **10 paid sick days per year** with no carryover. A medical certificate is required for sick leave exceeding 3 consecutive days. Exhausted sick leave may be followed by up to 30 days unpaid medical leave with HR approval."
    if "annual leave" in u or "vacation" in u or "holiday" in u:
        return "Full-time employees accrue **20 days of paid annual leave per calendar year**, credited quarterly (5 days/quarter). Up to 5 unused days carry over; the remainder is forfeited December 31st. Leave cannot be taken in the first 90 days of employment."
    if "parental" in u or "maternity" in u or "paternity" in u:
        return "**Primary caregivers** receive 16 weeks paid parental leave. **Secondary caregivers** receive 4 weeks. Leave must begin within 12 months of birth or adoption."
    if "bereavement" in u:
        return "Employees receive **5 paid days** for immediate family (spouse, child, parent, sibling) and **2 paid days** for extended family."
    if "remote" in u or "work from home" in u or "wfh" in u:
        return "Up to **3 days/week remote** with manager approval. Full remote requires VP approval, reviewed quarterly. Core hours: 10am–3pm local time."
    if "performance review" in u or "appraisal" in u:
        return "Performance reviews are **bi-annual**: June and December. Compensation adjustments tied to year-end review. Minimum 2 weeks notice before review."

    # ── Generic fallback ───────────────────────────────────────────────────
    return (
        "Based on the ingested Propgatics platform documents, I can answer questions about: "
        "the logistics dataset methodology, carrier performance benchmarks, KPI definitions, "
        "risk scoring methodology, incident types, HR policies, and the ORS API integration. "
        "Could you be more specific about what you'd like to know?"
    )
