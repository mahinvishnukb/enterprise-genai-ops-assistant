"""
Seeds the database with real logistics data from the Propgatics platform.

On first startup the seeder reads two CSV files bundled in the repository:
  data/shipments_sample.csv  — 5 000 rows sampled from the full 100K dataset
  data/incidents_sample.csv  — 1 000 rows sampled from the full 25K dataset

If the CSV files are missing (e.g. a bare-clone environment) the seeder falls
back to a small inline stub so the app still starts without crashing.

Run standalone:  python -m app.db.seed
"""
import csv
import datetime as dt
from pathlib import Path

from app.db.models import Base, Incident, OperationsData, Shipment
from app.db.session import SessionLocal, engine

# Resolve the data/ directory relative to the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"


def _parse_date(s: str) -> dt.date | None:
    if not s or s.lower() in ("none", "null", ""):
        return None
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def _parse_float(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _parse_int(s: str) -> int:
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def _seed_shipments(db) -> int:
    csv_path = _DATA_DIR / "shipments_sample.csv"
    if not csv_path.exists():
        print("[seed] shipments_sample.csv not found — using stub data")
        _seed_stub_shipments(db)
        return 0

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(Shipment(
                shipment_id=r["shipment_id"],
                tracking_number=r.get("tracking_number"),
                carrier=r.get("carrier"),
                origin=r.get("origin"),
                destination=r.get("destination"),
                distance_km=_parse_float(r.get("distance_km", "")),
                estimated_duration_hours=_parse_float(r.get("estimated_duration_hours", "")),
                shipment_date=_parse_date(r.get("shipment_date", "")),
                estimated_delivery_date=_parse_date(r.get("estimated_delivery_date", "")),
                actual_delivery_date=_parse_date(r.get("actual_delivery_date", "")),
                shipment_status=r.get("shipment_status"),
                delay_hours=_parse_float(r.get("delay_hours", "")),
                package_weight_kg=_parse_float(r.get("package_weight_kg", "")),
                package_type=r.get("package_type"),
                shipping_cost_cad=_parse_float(r.get("shipping_cost_cad", "")),
                priority_level=r.get("priority_level"),
                service_level=r.get("service_level"),
                customer_type=r.get("customer_type"),
                weather_condition=r.get("weather_condition"),
                traffic_level=r.get("traffic_level"),
                warehouse_id=r.get("warehouse_id"),
                driver_id=r.get("driver_id"),
                fuel_cost_cad=_parse_float(r.get("fuel_cost_cad", "")),
                delivery_cost_cad=_parse_float(r.get("delivery_cost_cad", "")),
                delay_reason=r.get("delay_reason"),
                on_time_delivery=_parse_int(r.get("on_time_delivery", "")),
                route_risk_score=_parse_float(r.get("route_risk_score", "")),
                risk_category=r.get("risk_category"),
                delivery_performance=r.get("delivery_performance"),
            ))

    # Batch insert in chunks of 500 for speed
    BATCH = 500
    for i in range(0, len(rows), BATCH):
        db.add_all(rows[i:i + BATCH])
        db.commit()
    print(f"[seed] inserted {len(rows)} shipment rows")
    return len(rows)


def _seed_incidents(db) -> int:
    csv_path = _DATA_DIR / "incidents_sample.csv"
    if not csv_path.exists():
        print("[seed] incidents_sample.csv not found — skipping incidents")
        return 0

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(Incident(
                incident_id=r["incident_id"],
                shipment_id=r.get("shipment_id"),
                tracking_number=r.get("tracking_number"),
                carrier=r.get("carrier"),
                origin=r.get("origin"),
                destination=r.get("destination"),
                incident_type=r.get("incident_type"),
                severity_level=r.get("severity_level"),
                incident_status=r.get("incident_status"),
                incident_date=r.get("incident_date"),
                delay_hours=_parse_float(r.get("delay_hours", "")),
                weather_condition=r.get("weather_condition"),
                traffic_level=r.get("traffic_level"),
                route_risk_score=_parse_float(r.get("route_risk_score", "")),
                estimated_financial_loss_cad=_parse_float(r.get("estimated_financial_loss_cad", "")),
                resolution_action=r.get("resolution_action"),
                resolution_time_hours=_parse_float(r.get("resolution_time_hours", "")),
                warehouse_id=r.get("warehouse_id"),
                driver_id=r.get("driver_id"),
            ))

    BATCH = 250
    for i in range(0, len(rows), BATCH):
        db.add_all(rows[i:i + BATCH])
        db.commit()
    print(f"[seed] inserted {len(rows)} incident rows")
    return len(rows)


def _seed_stub_shipments(db) -> None:
    """Minimal inline stub so the app boots without any CSV files present."""
    import datetime as dt2
    stubs = [
        Shipment(shipment_id="SHP000001", carrier="UPS", origin="Toronto",
                 destination="Vancouver", shipment_status="Delivered",
                 delay_hours=0, on_time_delivery=1, risk_category="Low",
                 delivery_performance="On Time",
                 shipment_date=dt2.date(2026, 3, 1)),
        Shipment(shipment_id="SHP000002", carrier="FedEx", origin="Calgary",
                 destination="Montreal", shipment_status="Delayed",
                 delay_hours=4.5, on_time_delivery=0, risk_category="Medium",
                 delivery_performance="Delayed",
                 shipment_date=dt2.date(2026, 3, 5)),
        Shipment(shipment_id="SHP000003", carrier="DHL", origin="Vancouver",
                 destination="Edmonton", shipment_status="Minor Delay",
                 delay_hours=1.2, on_time_delivery=0, risk_category="Low",
                 delivery_performance="Delayed",
                 shipment_date=dt2.date(2026, 3, 10)),
    ]
    db.add_all(stubs)
    db.commit()
    print("[seed] inserted 3 stub shipment rows")


def seed() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.query(Shipment).count() > 0:
            print("[seed] shipments already seeded, skipping.")
            return
        _seed_shipments(db)
        _seed_incidents(db)

        # migration compat: keep OperationsData seeded so older Render deployments
        # that still have that table don't error on startup.
        if db.query(OperationsData).count() == 0:
            import random, datetime as dt3
            CITIES = ["Toronto", "Vancouver", "Calgary", "Montreal"]
            for _ in range(10):
                o, d = random.sample(CITIES, 2)
                db.add(OperationsData(origin=o, destination=d, status="on_time",
                                      delay_days=0,
                                      shipped_at=dt3.date.today()))
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
