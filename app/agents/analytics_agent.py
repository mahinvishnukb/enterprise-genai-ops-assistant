"""
AnalyticsAgent — computes real SQL analytics over the Propgatics shipments
and incidents tables, then uses the LLM to narrate the findings.

This is the "LLM-as-narrator / code-first language-last" pattern:
  1. Run deterministic SQL queries for correctness and auditability.
  2. Pass the structured results to the LLM for plain-English synthesis.

Tables available:
  shipments  — 5 000 seeded rows (100K total), full enriched schema
  incidents  — 1 000 seeded rows (25K total), incident + financial data
"""
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.llm_client import LLMClient

NARRATE_PROMPT = (
    "REPORT_GENERATION: You are a senior logistics operations analyst. "
    "Given structured metrics below, write a concise professional insight (3-5 sentences). "
    "Highlight the most important finding first. Use specific numbers. "
    "Flag anything that looks like a risk or anomaly requiring action."
)


class AnalyticsAgent:
    def __init__(self, engine: Engine, llm: LLMClient | None = None):
        self.engine = engine
        self.llm = llm or LLMClient()

    def _query(self, sql: str) -> list[dict]:
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(r._mapping) for r in result]

    def compute(self, question: str) -> dict:
        q = question.lower()

        if any(w in q for w in ["incident", "damage", "lost", "customs hold", "failed delivery"]):
            return self._incident_analysis()
        if any(w in q for w in ["carrier", "ups", "fedex", "dhl", "purolator", "canada post"]):
            return self._carrier_analysis()
        if any(w in q for w in ["risk", "high risk", "critical", "risk score"]):
            return self._risk_analysis()
        if any(w in q for w in ["weather", "rain", "snow", "storm", "fog"]):
            return self._weather_impact()
        if any(w in q for w in ["delay", "late", "slow", "bottleneck", "worst route"]):
            return self._delay_analysis()
        if any(w in q for w in ["route", "popular", "busiest", "top route", "corridor"]):
            return self._route_analysis()
        if any(w in q for w in ["trend", "week", "month", "over time", "history", "monthly", "weekly"]):
            return self._trend_analysis()
        if any(w in q for w in ["cancel", "cancelled"]):
            return self._cancellation_analysis()
        if any(w in q for w in ["kpi", "summary", "overview", "dashboard", "report", "performance"]):
            return self._kpi_summary()
        return self._kpi_summary()

    # ── KPI summary ────────────────────────────────────────────────────────

    def _kpi_summary(self) -> dict:
        rows = self._query("""
            SELECT
                shipment_status,
                COUNT(*) as count,
                ROUND(AVG(delay_hours), 2) as avg_delay_hours,
                ROUND(AVG(shipping_cost_cad), 2) as avg_cost_cad
            FROM shipments
            GROUP BY shipment_status
            ORDER BY count DESC
        """)
        total = sum(r["count"] for r in rows)
        on_time_count = sum(r["count"] for r in rows if r["shipment_status"] == "Delivered")
        delayed_count = sum(
            r["count"] for r in rows
            if r["shipment_status"] in ("Delayed", "Minor Delay", "Critical Delay")
        )
        avg_delay = self._query(
            "SELECT ROUND(AVG(delay_hours),2) as avg FROM shipments WHERE delay_hours > 0"
        )
        incident_count = self._query("SELECT COUNT(*) as n FROM incidents")[0]["n"]

        metrics = {
            "Total shipments": total,
            "Delivered (on time)": f"{on_time_count} ({round(on_time_count/max(total,1)*100,1)}%)",
            "Delayed (any severity)": f"{delayed_count} ({round(delayed_count/max(total,1)*100,1)}%)",
            "Avg delay (delayed only)": f"{avg_delay[0]['avg'] if avg_delay else 0} hours",
            "Total incidents": incident_count,
        }
        narrative = self.llm.chat(system=NARRATE_PROMPT, user=f"KPI Summary: {metrics}")
        return {"answer": narrative, "metrics": metrics, "rows": rows,
                "row_count": len(rows), "analysis_type": "kpi_summary"}

    # ── Carrier performance ────────────────────────────────────────────────

    def _carrier_analysis(self) -> dict:
        rows = self._query("""
            SELECT
                carrier,
                COUNT(*) as total_shipments,
                ROUND(AVG(on_time_delivery)*100, 1) as on_time_pct,
                ROUND(AVG(delay_hours), 2) as avg_delay_hours,
                ROUND(AVG(shipping_cost_cad), 2) as avg_cost_cad,
                ROUND(AVG(route_risk_score), 2) as avg_risk_score
            FROM shipments
            GROUP BY carrier
            ORDER BY on_time_pct DESC
        """)
        best = rows[0] if rows else {}
        worst = rows[-1] if rows else {}
        metrics = {
            "Best on-time carrier": f"{best.get('carrier')} ({best.get('on_time_pct')}%)",
            "Worst on-time carrier": f"{worst.get('carrier')} ({worst.get('on_time_pct')}%)",
            "Performance spread": f"{round((best.get('on_time_pct',0) - worst.get('on_time_pct',0)),2)}%",
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"Carrier performance breakdown: {rows}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows,
                "row_count": len(rows), "analysis_type": "carrier_analysis"}

    # ── Delay analysis ─────────────────────────────────────────────────────

    def _delay_analysis(self) -> dict:
        rows = self._query("""
            SELECT
                origin, destination,
                COUNT(*) as total_shipments,
                SUM(CASE WHEN shipment_status IN ('Delayed','Minor Delay','Critical Delay')
                    THEN 1 ELSE 0 END) as delayed_count,
                ROUND(AVG(CASE WHEN delay_hours > 0 THEN delay_hours END), 2) as avg_delay_hours
            FROM shipments
            GROUP BY origin, destination
            HAVING delayed_count > 0
            ORDER BY avg_delay_hours DESC
            LIMIT 10
        """)
        delay_reason_rows = self._query("""
            SELECT delay_reason, COUNT(*) as count
            FROM shipments
            WHERE delay_reason != 'None' AND delay_reason IS NOT NULL AND delay_reason != ''
            GROUP BY delay_reason
            ORDER BY count DESC
            LIMIT 5
        """)
        metrics = {
            "Worst delay corridor": f"{rows[0]['origin']} → {rows[0]['destination']}" if rows else "N/A",
            "Avg delay on worst route": f"{rows[0]['avg_delay_hours']} h" if rows else "N/A",
            "Top delay reason": delay_reason_rows[0]["delay_reason"] if delay_reason_rows else "N/A",
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"Delay hotspots: {rows[:5]}. Delay reasons: {delay_reason_rows}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows,
                "row_count": len(rows), "analysis_type": "delay_analysis"}

    # ── Route analysis ─────────────────────────────────────────────────────

    def _route_analysis(self) -> dict:
        rows = self._query("""
            SELECT
                origin, destination,
                COUNT(*) as shipments,
                ROUND(AVG(on_time_delivery)*100, 1) as on_time_pct,
                ROUND(AVG(delay_hours), 2) as avg_delay_hours,
                ROUND(AVG(distance_km), 1) as avg_distance_km
            FROM shipments
            GROUP BY origin, destination
            ORDER BY shipments DESC
            LIMIT 12
        """)
        metrics = {
            "Busiest route": f"{rows[0]['origin']} → {rows[0]['destination']}" if rows else "N/A",
            "Busiest route volume": rows[0]["shipments"] if rows else 0,
            "Busiest route on-time": f"{rows[0]['on_time_pct']}%" if rows else "N/A",
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"Top routes by volume: {rows}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows,
                "row_count": len(rows), "analysis_type": "route_analysis"}

    # ── Weekly trend ───────────────────────────────────────────────────────

    def _trend_analysis(self) -> dict:
        rows = self._query("""
            SELECT
                strftime('%Y-%m', shipment_date) as month,
                COUNT(*) as shipments,
                SUM(CASE WHEN shipment_status IN ('Delayed','Minor Delay','Critical Delay')
                    THEN 1 ELSE 0 END) as delays,
                ROUND(AVG(on_time_delivery)*100, 1) as on_time_pct
            FROM shipments
            WHERE shipment_date IS NOT NULL
            GROUP BY month
            ORDER BY month DESC
            LIMIT 6
        """)
        metrics = {
            "Months analyzed": len(rows),
            "Latest month shipments": rows[0]["shipments"] if rows else 0,
            "Latest month on-time": f"{rows[0]['on_time_pct']}%" if rows else "N/A",
            "Latest month delays": rows[0]["delays"] if rows else 0,
        }
        narrative = self.llm.chat(system=NARRATE_PROMPT, user=f"Monthly shipment trend: {rows}")
        return {"answer": narrative, "metrics": metrics, "rows": rows,
                "row_count": len(rows), "analysis_type": "trend_analysis"}

    # ── Cancellation analysis (maps to Critical Delay / terminal statuses) ─

    def _cancellation_analysis(self) -> dict:
        rows = self._query("""
            SELECT
                origin,
                COUNT(*) as critical_delays,
                ROUND(AVG(delay_hours), 2) as avg_delay_hours
            FROM shipments
            WHERE shipment_status = 'Critical Delay'
            GROUP BY origin
            ORDER BY critical_delays DESC
        """)
        total = sum(r["critical_delays"] for r in rows)
        metrics = {
            "Total critical delays": total,
            "Top origin for critical delays": rows[0]["origin"] if rows else "N/A",
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"Critical delay analysis by origin: {rows}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows,
                "row_count": len(rows), "analysis_type": "critical_delay_analysis"}

    # ── Incident analysis ──────────────────────────────────────────────────

    def _incident_analysis(self) -> dict:
        rows = self._query("""
            SELECT
                incident_type,
                COUNT(*) as count,
                ROUND(AVG(estimated_financial_loss_cad), 2) as avg_loss_cad,
                ROUND(AVG(resolution_time_hours), 1) as avg_resolution_hours
            FROM incidents
            GROUP BY incident_type
            ORDER BY count DESC
        """)
        carrier_rows = self._query("""
            SELECT carrier, COUNT(*) as incidents,
                   ROUND(SUM(estimated_financial_loss_cad), 2) as total_loss_cad
            FROM incidents
            GROUP BY carrier
            ORDER BY incidents DESC
        """)
        metrics = {
            "Most common incident": rows[0]["incident_type"] if rows else "N/A",
            "Total incidents": sum(r["count"] for r in rows),
            "Avg financial loss": f"CAD ${rows[0]['avg_loss_cad']:.2f}" if rows else "N/A",
            "Highest-incident carrier": carrier_rows[0]["carrier"] if carrier_rows else "N/A",
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"Incident breakdown by type: {rows}. By carrier: {carrier_rows}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows,
                "row_count": len(rows), "analysis_type": "incident_analysis"}

    # ── Risk analysis ──────────────────────────────────────────────────────

    def _risk_analysis(self) -> dict:
        rows = self._query("""
            SELECT
                risk_category,
                COUNT(*) as count,
                ROUND(AVG(route_risk_score), 2) as avg_risk_score,
                ROUND(AVG(delay_hours), 2) as avg_delay_hours
            FROM shipments
            GROUP BY risk_category
            ORDER BY avg_risk_score DESC
        """)
        top_routes = self._query("""
            SELECT origin, destination,
                   ROUND(AVG(route_risk_score), 2) as avg_risk,
                   COUNT(*) as shipments
            FROM shipments
            WHERE risk_category IN ('High','Critical')
            GROUP BY origin, destination
            ORDER BY avg_risk DESC
            LIMIT 5
        """)
        high_risk = sum(r["count"] for r in rows if r["risk_category"] in ("High", "Critical"))
        total = sum(r["count"] for r in rows)
        metrics = {
            "High/Critical risk shipments": f"{high_risk} ({round(high_risk/max(total,1)*100,1)}%)",
            "Riskiest route": f"{top_routes[0]['origin']} → {top_routes[0]['destination']}" if top_routes else "N/A",
            "Avg risk score (all)": self._query("SELECT ROUND(AVG(route_risk_score),2) as s FROM shipments")[0]["s"],
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"Risk category breakdown: {rows}. Top risky routes: {top_routes}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows,
                "row_count": len(rows), "analysis_type": "risk_analysis"}

    # ── Weather impact ─────────────────────────────────────────────────────

    def _weather_impact(self) -> dict:
        rows = self._query("""
            SELECT
                weather_condition,
                COUNT(*) as shipments,
                SUM(CASE WHEN shipment_status IN ('Delayed','Minor Delay','Critical Delay')
                    THEN 1 ELSE 0 END) as delays,
                ROUND(AVG(delay_hours), 2) as avg_delay_hours,
                ROUND(AVG(on_time_delivery)*100, 1) as on_time_pct
            FROM shipments
            GROUP BY weather_condition
            ORDER BY avg_delay_hours DESC
        """)
        worst = rows[0] if rows else {}
        metrics = {
            "Worst weather for delays": worst.get("weather_condition", "N/A"),
            "Avg delay in worst condition": f"{worst.get('avg_delay_hours', 0)} h",
            "On-time rate in worst condition": f"{worst.get('on_time_pct', 0)}%",
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"Weather impact on shipments: {rows}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows,
                "row_count": len(rows), "analysis_type": "weather_impact"}
