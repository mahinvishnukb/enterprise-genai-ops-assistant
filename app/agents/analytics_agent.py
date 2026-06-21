"""
AnalyticsAgent — computes real pandas/SQL analytics over operations_data.

Unlike SQLAgent (which returns raw rows), AnalyticsAgent synthesizes insights:
trends over time, top routes, delay hotspots, cancellation rates, KPIs.
It runs the actual computation in Python (not just LLM generation) and then
uses the LLM to narrate the findings in plain English — a pattern sometimes
called "LLM-as-narrator" or "code-first, language-last."

This is the pattern behind most production AI analytics tools: deterministic
computation for correctness, LLM for communication.
"""
import datetime as dt

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.llm_client import LLMClient

NARRATE_PROMPT = (
    "REPORT_GENERATION: You are an enterprise operations analyst. "
    "Given structured metrics below, write a concise professional insight (3-5 sentences). "
    "Highlight the most important finding first. Use specific numbers. "
    "Flag anything that looks like a risk or anomaly."
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

        # Route to specific analytics based on question intent
        if any(w in q for w in ["delay", "late", "slow", "bottleneck"]):
            return self._delay_analysis()
        if any(w in q for w in ["route", "popular", "busiest", "top"]):
            return self._route_analysis()
        if any(w in q for w in ["trend", "week", "month", "over time", "history"]):
            return self._trend_analysis()
        if any(w in q for w in ["cancel", "cancelled"]):
            return self._cancellation_analysis()
        if any(w in q for w in ["kpi", "summary", "overview", "dashboard", "report"]):
            return self._kpi_summary()
        return self._kpi_summary()

    def _kpi_summary(self) -> dict:
        rows = self._query("""
            SELECT
                status,
                COUNT(*) as count,
                ROUND(AVG(delay_days), 1) as avg_delay
            FROM operations_data
            GROUP BY status
        """)
        total = sum(r["count"] for r in rows)
        delayed = next((r for r in rows if r["status"] == "delayed"), {})
        on_time = next((r for r in rows if r["status"] == "on_time"), {})
        cancelled = next((r for r in rows if r["status"] == "cancelled"), {})

        metrics = {
            "Total shipments": total,
            "On-time": f"{on_time.get('count', 0)} ({round(on_time.get('count', 0)/max(total,1)*100)}%)",
            "Delayed": f"{delayed.get('count', 0)} ({round(delayed.get('count', 0)/max(total,1)*100)}%)",
            "Cancelled": f"{cancelled.get('count', 0)} ({round(cancelled.get('count', 0)/max(total,1)*100)}%)",
            "Avg delay (delayed only)": f"{delayed.get('avg_delay', 0)} days",
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"KPI Summary metrics: {metrics}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows, "row_count": len(rows), "analysis_type": "kpi_summary"}

    def _delay_analysis(self) -> dict:
        rows = self._query("""
            SELECT origin, destination,
                   COUNT(*) as total,
                   SUM(CASE WHEN status='delayed' THEN 1 ELSE 0 END) as delayed,
                   ROUND(AVG(CASE WHEN status='delayed' THEN delay_days ELSE NULL END), 1) as avg_delay_days
            FROM operations_data
            GROUP BY origin, destination
            HAVING delayed > 0
            ORDER BY delayed DESC
            LIMIT 10
        """)
        metrics = {
            "Routes analyzed": len(rows),
            "Worst route": f"{rows[0]['origin']} → {rows[0]['destination']}" if rows else "N/A",
            "Max delays on worst route": rows[0]["delayed"] if rows else 0,
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"Delay hotspot analysis: {metrics}. Top routes: {rows[:3]}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows, "row_count": len(rows), "analysis_type": "delay_analysis"}

    def _route_analysis(self) -> dict:
        rows = self._query("""
            SELECT origin, destination, COUNT(*) as shipments,
                   ROUND(SUM(CASE WHEN status='delayed' THEN 1.0 ELSE 0 END)/COUNT(*)*100, 1) as delay_rate_pct
            FROM operations_data
            GROUP BY origin, destination
            ORDER BY shipments DESC
            LIMIT 10
        """)
        metrics = {
            "Top route": f"{rows[0]['origin']} → {rows[0]['destination']}" if rows else "N/A",
            "Top route shipments": rows[0]["shipments"] if rows else 0,
            "Top route delay rate": f"{rows[0]['delay_rate_pct']}%" if rows else "N/A",
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"Route analysis: {metrics}. All routes: {rows}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows, "row_count": len(rows), "analysis_type": "route_analysis"}

    def _trend_analysis(self) -> dict:
        rows = self._query("""
            SELECT
                strftime('%Y-%W', shipped_at) as week,
                COUNT(*) as shipments,
                SUM(CASE WHEN status='delayed' THEN 1 ELSE 0 END) as delays
            FROM operations_data
            GROUP BY week
            ORDER BY week DESC
            LIMIT 8
        """)
        metrics = {
            "Weeks analyzed": len(rows),
            "Latest week shipments": rows[0]["shipments"] if rows else 0,
            "Latest week delays": rows[0]["delays"] if rows else 0,
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"Weekly trend: {rows}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows, "row_count": len(rows), "analysis_type": "trend_analysis"}

    def _cancellation_analysis(self) -> dict:
        rows = self._query("""
            SELECT origin, COUNT(*) as cancellations
            FROM operations_data
            WHERE status = 'cancelled'
            GROUP BY origin
            ORDER BY cancellations DESC
        """)
        total_cancelled = sum(r["cancellations"] for r in rows)
        metrics = {
            "Total cancelled": total_cancelled,
            "Top origin for cancellations": rows[0]["origin"] if rows else "N/A",
        }
        narrative = self.llm.chat(
            system=NARRATE_PROMPT,
            user=f"Cancellation analysis: {metrics}. By origin: {rows}"
        )
        return {"answer": narrative, "metrics": metrics, "rows": rows, "row_count": len(rows), "analysis_type": "cancellation_analysis"}
