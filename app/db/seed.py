"""
Seeds the database with real logistics data from the Propgatics platform.

On first startup the seeder reads two CSV files bundled in the repository:
  data/shipments_sample.csv  — 5 000 rows sampled from the full 100K dataset
  data/incidents_sample.csv  — 1 000 rows sampled from the full 25K dataset

If the CSV files are missing the seeder falls back to 500 shipment stubs and
100 incident stubs so the app still starts with meaningful analytics data.

Run standalone:  python -m app.db.seed
"""
import csv
import datetime as dt
from pathlib import Path

from app.db.models import Base, Incident, OperationsData, Shipment
from app.db.session import SessionLocal, engine

# Resolve the data/ directory — try every plausible location so the CSV
# loads reliably on Render, Railway, Fly, local dev, and Docker.
import os as _os

def _find_data_dir() -> Path:
    # Env override wins — set DATA_DIR in Render Dashboard or render.yaml
    _env = _os.environ.get("DATA_DIR", "").strip()
    if _env:
        p = Path(_env)
        if p.exists() and (p / "shipments_sample.csv").exists():
            return p

    # Render sets RENDER=true — use the known Render project path
    if _os.environ.get("RENDER"):
        p = Path("/opt/render/project/src/data")
        if p.exists() and (p / "shipments_sample.csv").exists():
            return p

    # Standard candidates: relative to this file (most reliable), then CWD
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "data",
        Path.cwd() / "data",
    ]
    for p in candidates:
        if p.exists() and (p / "shipments_sample.csv").exists():
            return p

    # Fallback — will be reported as missing
    return Path(__file__).resolve().parent.parent.parent / "data"

_DATA_DIR: Path = _find_data_dir()
_CSV_AVAILABLE: bool = (_DATA_DIR / "shipments_sample.csv").exists()
print(f"[seed] data dir → {_DATA_DIR} | RENDER={_os.environ.get('RENDER','n/a')} "
      f"| csv={'FOUND ✓' if _CSV_AVAILABLE else 'MISSING — will use stubs'}")


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

    BATCH = 500
    for i in range(0, len(rows), BATCH):
        db.add_all(rows[i:i + BATCH])
        db.commit()
    print(f"[seed] inserted {len(rows)} shipment rows from CSV")
    return len(rows)


def _seed_incidents(db) -> int:
    csv_path = _DATA_DIR / "incidents_sample.csv"
    if not csv_path.exists():
        print("[seed] incidents_sample.csv not found — using stub data")
        _seed_stub_incidents(db)
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
    print(f"[seed] inserted {len(rows)} incident rows from CSV")
    return len(rows)


# ─── Comprehensive fallback stubs (500 shipments + 100 incidents) ─────────────
# Generated programmatically: no hardcoded tuples, covers all carriers, cities,
# statuses, weather, risk, and 6 months so all analytics still work without CSV.

def _seed_stub_shipments(db) -> None:
    """Generate 500 deterministic stub shipments covering all analytical dimensions."""
    import random as _rnd
    _rnd.seed(42)

    _CARRIERS   = ["UPS", "FedEx", "DHL", "Canada Post", "Purolator"]
    _CITIES     = ["Toronto", "Vancouver", "Calgary", "Montreal", "Edmonton",
                   "Halifax", "Moncton", "Ottawa", "Kelowna", "Winnipeg"]
    _STATUSES   = ["Delivered", "Minor Delay", "Delayed", "Critical Delay"]
    _SWTS       = [0.60, 0.20, 0.15, 0.05]      # status weights
    _WEATHERS   = ["Clear", "Cloudy", "Rain", "Fog", "Snow", "Storm"]
    _WWTS       = [0.38, 0.22, 0.16, 0.10, 0.09, 0.05]  # weather weights
    _TRAFFIC    = ["Low", "Medium", "High"]
    _PRIORITIES = ["Standard", "Express", "Same-Day"]
    _SERVICES   = ["Economy", "Two-Day", "Priority", "Overnight"]
    _PKG_TYPES  = ["Small Parcel", "Large Parcel", "Pallet", "Envelope"]
    _CUST_TYPES = ["Business", "Individual"]
    _DELAY_RSN  = ["Weather", "Traffic", "Mechanical", "Customs", "Strike"]
    _BASE_DATE  = dt.date(2026, 1, 1)
    _RISK_BONUS = {"Clear": 0, "Cloudy": 4, "Rain": 12, "Fog": 17, "Snow": 27, "Storm": 47}
    _TRAFFIC_ADD = {"Low": 0, "Medium": 5, "High": 14}

    rows = []
    for i in range(500):
        carrier  = _CARRIERS[i % len(_CARRIERS)]
        ci, cj   = i % len(_CITIES), (i * 3 + 7) % len(_CITIES)
        if ci == cj:
            cj = (cj + 1) % len(_CITIES)
        origin, dest = _CITIES[ci], _CITIES[cj]

        status   = _rnd.choices(_STATUSES, weights=_SWTS)[0]
        weather  = _rnd.choices(_WEATHERS, weights=_WWTS)[0]
        traffic  = _TRAFFIC[i % 3]

        if status == "Delivered":
            delay_h, on_time = 0.0, 1
        elif status == "Minor Delay":
            delay_h, on_time = round(_rnd.uniform(0.5, 3.0), 1), 0
        elif status == "Delayed":
            delay_h, on_time = round(_rnd.uniform(3.0, 8.0), 1), 0
        else:
            delay_h, on_time = round(_rnd.uniform(8.0, 24.0), 1), 0

        risk = round(min(99.9, 8 + _RISK_BONUS[weather] + _TRAFFIC_ADD[traffic] + _rnd.uniform(-2, 4)), 1)
        risk_cat = "Low" if risk < 20 else "Medium" if risk < 40 else "High" if risk < 60 else "Critical"

        ship_date = _BASE_DATE + dt.timedelta(days=i % 181)
        cost      = round(60 + _rnd.uniform(0, 35), 2)

        rows.append(Shipment(
            shipment_id=f"SHP{i+1:06d}",
            carrier=carrier, origin=origin, destination=dest,
            shipment_status=status, delay_hours=delay_h, on_time_delivery=on_time,
            route_risk_score=risk, risk_category=risk_cat,
            weather_condition=weather, traffic_level=traffic,
            shipping_cost_cad=cost, delivery_cost_cad=round(cost * 2.54, 2),
            fuel_cost_cad=round(cost * 0.18, 2),
            shipment_date=ship_date,
            priority_level=_PRIORITIES[i % 3],
            service_level=_SERVICES[i % 4],
            package_type=_PKG_TYPES[i % 4],
            customer_type=_CUST_TYPES[i % 2],
            delay_reason="None" if on_time else _DELAY_RSN[i % 5],
            package_weight_kg=round(_rnd.uniform(0.1, 50.0), 1),
            distance_km=round(_rnd.uniform(80, 4600), 1),
            estimated_duration_hours=round(_rnd.uniform(1, 80), 1),
            warehouse_id=f"WH-{origin[:3].upper()}-{(i % 3) + 1:03d}",
            driver_id=f"DRV{(i % 200) + 1:05d}",
        ))

    BATCH = 100
    for b in range(0, len(rows), BATCH):
        db.add_all(rows[b:b + BATCH])
        db.commit()
    print(f"[seed] inserted {len(rows)} stub shipment rows")


def _seed_stub_incidents(db) -> None:
    """Generate 100 deterministic stub incidents covering all types and severities."""
    import random as _rnd
    _rnd.seed(42)

    _INC_TYPES = [
        "Failed Delivery Attempt", "Damaged Shipment", "Lost Package",
        "Customs Hold", "Weather Delay", "Mechanical Failure",
        "Address Error", "Warehouse Processing Delay", "Traffic Disruption",
    ]
    _SEVS     = ["Low", "Medium", "High", "Critical"]
    _SEV_WTS  = [0.41, 0.34, 0.15, 0.10]
    _IST      = ["Resolved", "Under Investigation", "Open"]
    _IST_WTS  = [0.65, 0.25, 0.10]
    _CARRIERS = ["UPS", "FedEx", "DHL", "Canada Post", "Purolator"]
    _CITIES   = ["Toronto", "Vancouver", "Calgary", "Montreal", "Edmonton",
                 "Halifax", "Moncton", "Ottawa", "Kelowna", "Winnipeg"]
    _LOSS     = {"Low":(300,1200), "Medium":(900,2000), "High":(1800,2700), "Critical":(2500,3600)}
    _RES      = {"Low":(10,48), "Medium":(36,84), "High":(72,120), "Critical":(84,148)}

    stubs = []
    for i in range(100):
        sev = _rnd.choices(_SEVS, weights=_SEV_WTS)[0]
        ist = _rnd.choices(_IST, weights=_IST_WTS)[0]
        ci, cj = i % len(_CITIES), (i * 3 + 5) % len(_CITIES)
        if ci == cj:
            cj = (cj + 1) % len(_CITIES)
        stubs.append(Incident(
            incident_id=f"INC{i+1:06d}",
            shipment_id=f"SHP{(i % 500) + 1:06d}",
            carrier=_CARRIERS[i % 5],
            origin=_CITIES[ci], destination=_CITIES[cj],
            incident_type=_INC_TYPES[i % len(_INC_TYPES)],
            severity_level=sev,
            incident_status=ist,
            delay_hours=round(_rnd.uniform(0, 16), 1),
            estimated_financial_loss_cad=round(_rnd.uniform(*_LOSS[sev]), 2),
            resolution_time_hours=round(_rnd.uniform(*_RES[sev]), 1) if ist == "Resolved" else 0.0,
            warehouse_id=f"WH-{_CITIES[ci][:3].upper()}-001",
            driver_id=f"DRV{(i % 100) + 1:05d}",
        ))
    db.add_all(stubs)
    db.commit()
    print(f"[seed] inserted {len(stubs)} stub incident rows")


def seed() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        current = db.query(Shipment).count()

        # CSV data has 5000 rows → anything >= 1000 means full CSV is loaded.
        if current >= 1000:
            print(f"[seed] {current} rows already present — skipping.")
            return

        # 400-999 means stub rows (500) are loaded.
        # Keep stubs if no CSV; upgrade if CSV is available.
        if current >= 400:
            if not _CSV_AVAILABLE:
                print(f"[seed] {current} stub rows, no CSV found — keeping stubs.")
                return
            # CSV is available: clear stubs and reload from CSV.
            print(f"[seed] {current} stub rows found but CSV is available — upgrading to full CSV load")
            db.query(Shipment).delete()
            db.query(Incident).delete()
            db.commit()

        elif current > 0:
            # Stale legacy rows — always clear and reload.
            print(f"[seed] clearing {current} legacy rows and reloading")
            db.query(Shipment).delete()
            db.query(Incident).delete()
            db.commit()

        _seed_shipments(db)
        _seed_incidents(db)

        # migration compat: keep OperationsData seeded so older deployments don't error.
        if db.query(OperationsData).count() == 0:
            import random
            CITIES = ["Toronto", "Vancouver", "Calgary", "Montreal"]
            for _ in range(10):
                o, d = random.sample(CITIES, 2)
                db.add(OperationsData(origin=o, destination=d, status="on_time",
                                      delay_days=0, shipped_at=dt.date.today()))
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
