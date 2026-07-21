"""
Seeds the database with real logistics data from the Propgatics platform.

On first startup the seeder reads two CSV files bundled in the repository:
  data/shipments_sample.csv  — 5 000 rows sampled from the full 100K dataset
  data/incidents_sample.csv  — 1 000 rows sampled from the full 25K dataset

If the CSV files are missing the seeder falls back to 50 shipment stubs and
20 incident stubs so the app still starts with meaningful analytics data.

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


# ─── Comprehensive fallback stubs ─────────────────────────────────────────────
# 50 shipments covering all 5 carriers, 4 statuses, 4 risk categories,
# 6 weather conditions, and 6 months of dates for trend analysis.

def _seed_stub_shipments(db) -> None:
    """50-row stub with full carrier/status/weather/risk coverage."""
    # fmt: off
    # (id, carrier, origin, dest, status, delay_h, on_time, risk_score, risk_cat, weather, cost_cad, traffic, date)
    _D = [
        # ── UPS ───────────────────────────────────────────────────────────
        ("SHP000001","UPS","Toronto","Vancouver","Delivered",0,1,12.5,"Low","Clear",77.3,"Low",dt.date(2026,1,3)),
        ("SHP000002","UPS","Calgary","Montreal","Delivered",0,1,18.2,"Low","Cloudy",74.5,"Low",dt.date(2026,1,15)),
        ("SHP000003","UPS","Ottawa","Edmonton","Delivered",0,1,9.8,"Low","Clear",81.2,"Low",dt.date(2026,2,1)),
        ("SHP000004","UPS","Toronto","Calgary","Minor Delay",1.5,0,22.4,"Medium","Rain",79.0,"Medium",dt.date(2026,2,14)),
        ("SHP000005","UPS","Vancouver","Toronto","Minor Delay",2.1,0,28.7,"Medium","Cloudy",76.8,"High",dt.date(2026,2,28)),
        ("SHP000006","UPS","Montreal","Vancouver","Delivered",0,1,15.3,"Low","Clear",83.1,"Low",dt.date(2026,3,10)),
        ("SHP000007","UPS","Halifax","Calgary","Delayed",5.2,0,45.6,"High","Storm",72.4,"High",dt.date(2026,3,22)),
        ("SHP000008","UPS","Edmonton","Toronto","Delivered",0,1,11.2,"Low","Clear",78.9,"Medium",dt.date(2026,4,5)),
        ("SHP000009","UPS","Toronto","Montreal","Delivered",0,1,8.5,"Low","Clear",75.6,"Low",dt.date(2026,4,18)),
        ("SHP000010","UPS","Vancouver","Calgary","Delivered",0,1,19.1,"Low","Fog",80.3,"Medium",dt.date(2026,5,2)),
        # ── FedEx ─────────────────────────────────────────────────────────
        ("SHP000011","FedEx","Toronto","Calgary","Delivered",0,1,14.2,"Low","Clear",76.1,"Low",dt.date(2026,1,5)),
        ("SHP000012","FedEx","Calgary","Vancouver","Minor Delay",1.8,0,24.5,"Medium","Snow",73.8,"Medium",dt.date(2026,1,20)),
        ("SHP000013","FedEx","Montreal","Edmonton","Delivered",0,1,10.9,"Low","Clear",82.4,"Low",dt.date(2026,2,5)),
        ("SHP000014","FedEx","Ottawa","Toronto","Delayed",4.5,0,38.7,"High","Storm",70.5,"High",dt.date(2026,2,18)),
        ("SHP000015","FedEx","Vancouver","Montreal","Delivered",0,1,13.6,"Low","Cloudy",78.2,"Low",dt.date(2026,3,3)),
        ("SHP000016","FedEx","Toronto","Edmonton","Minor Delay",2.3,0,31.4,"Medium","Rain",77.9,"Medium",dt.date(2026,3,15)),
        ("SHP000017","FedEx","Calgary","Ottawa","Delivered",0,1,17.8,"Low","Clear",74.7,"Low",dt.date(2026,4,1)),
        ("SHP000018","FedEx","Edmonton","Vancouver","Critical Delay",12.5,0,68.3,"Critical","Storm",69.2,"High",dt.date(2026,4,14)),
        ("SHP000019","FedEx","Halifax","Toronto","Delivered",0,1,12.1,"Low","Clear",80.6,"Low",dt.date(2026,4,28)),
        ("SHP000020","FedEx","Toronto","Vancouver","Delivered",0,1,9.7,"Low","Clear",76.4,"Medium",dt.date(2026,5,8)),
        # ── DHL ───────────────────────────────────────────────────────────
        ("SHP000021","DHL","Vancouver","Toronto","Delivered",0,1,11.4,"Low","Clear",79.5,"Low",dt.date(2026,1,8)),
        ("SHP000022","DHL","Toronto","Montreal","Delivered",0,1,7.8,"Low","Clear",74.3,"Low",dt.date(2026,1,22)),
        ("SHP000023","DHL","Calgary","Toronto","Minor Delay",1.2,0,21.6,"Medium","Fog",76.8,"Medium",dt.date(2026,2,8)),
        ("SHP000024","DHL","Montreal","Calgary","Delivered",0,1,16.3,"Low","Clear",81.1,"Low",dt.date(2026,2,22)),
        ("SHP000025","DHL","Ottawa","Vancouver","Delayed",3.8,0,42.1,"High","Snow",73.2,"High",dt.date(2026,3,7)),
        ("SHP000026","DHL","Edmonton","Montreal","Delivered",0,1,13.9,"Low","Cloudy",78.7,"Low",dt.date(2026,3,20)),
        ("SHP000027","DHL","Toronto","Ottawa","Delivered",0,1,8.1,"Low","Clear",75.9,"Low",dt.date(2026,4,3)),
        ("SHP000028","DHL","Vancouver","Calgary","Delivered",0,1,19.5,"Low","Rain",80.2,"Medium",dt.date(2026,4,17)),
        ("SHP000029","DHL","Calgary","Halifax","Minor Delay",2.7,0,33.8,"Medium","Storm",72.6,"High",dt.date(2026,5,1)),
        ("SHP000030","DHL","Montreal","Toronto","Delivered",0,1,10.2,"Low","Clear",77.4,"Low",dt.date(2026,5,12)),
        # ── Canada Post ───────────────────────────────────────────────────
        ("SHP000031","Canada Post","Ottawa","Montreal","Delivered",0,1,6.5,"Low","Clear",73.8,"Low",dt.date(2026,1,10)),
        ("SHP000032","Canada Post","Toronto","Halifax","Delivered",0,1,14.7,"Low","Clear",78.3,"Low",dt.date(2026,1,25)),
        ("SHP000033","Canada Post","Vancouver","Edmonton","Delivered",0,1,11.8,"Low","Cloudy",75.1,"Medium",dt.date(2026,2,10)),
        ("SHP000034","Canada Post","Calgary","Ottawa","Minor Delay",1.9,0,26.3,"Medium","Snow",76.4,"Medium",dt.date(2026,2,24)),
        ("SHP000035","Canada Post","Montreal","Halifax","Delivered",0,1,9.4,"Low","Clear",80.8,"Low",dt.date(2026,3,9)),
        ("SHP000036","Canada Post","Edmonton","Toronto","Delivered",0,1,15.2,"Low","Clear",74.9,"Low",dt.date(2026,3,23)),
        ("SHP000037","Canada Post","Toronto","Calgary","Delivered",0,1,17.6,"Low","Rain",79.3,"Medium",dt.date(2026,4,6)),
        ("SHP000038","Canada Post","Vancouver","Montreal","Delayed",6.1,0,47.8,"High","Storm",71.5,"High",dt.date(2026,4,20)),
        ("SHP000039","Canada Post","Ottawa","Edmonton","Delivered",0,1,12.9,"Low","Clear",76.7,"Low",dt.date(2026,5,4)),
        ("SHP000040","Canada Post","Halifax","Vancouver","Delivered",0,1,10.6,"Low","Fog",78.1,"Medium",dt.date(2026,5,15)),
        # ── Purolator ─────────────────────────────────────────────────────
        ("SHP000041","Purolator","Calgary","Toronto","Delivered",0,1,15.8,"Low","Clear",77.8,"Low",dt.date(2026,1,12)),
        ("SHP000042","Purolator","Montreal","Ottawa","Delivered",0,1,8.3,"Low","Clear",74.2,"Low",dt.date(2026,1,27)),
        ("SHP000043","Purolator","Toronto","Edmonton","Minor Delay",2.4,0,29.6,"Medium","Cloudy",76.5,"Medium",dt.date(2026,2,12)),
        ("SHP000044","Purolator","Vancouver","Halifax","Delivered",0,1,18.4,"Low","Clear",81.5,"Low",dt.date(2026,2,26)),
        ("SHP000045","Purolator","Edmonton","Calgary","Delivered",0,1,7.2,"Low","Clear",75.3,"Low",dt.date(2026,3,12)),
        ("SHP000046","Purolator","Ottawa","Vancouver","Critical Delay",11.8,0,72.5,"Critical","Storm",68.9,"High",dt.date(2026,3,25)),
        ("SHP000047","Purolator","Halifax","Montreal","Delivered",0,1,11.5,"Low","Cloudy",79.7,"Medium",dt.date(2026,4,8)),
        ("SHP000048","Purolator","Calgary","Edmonton","Delivered",0,1,5.9,"Low","Clear",73.4,"Low",dt.date(2026,4,22)),
        ("SHP000049","Purolator","Toronto","Vancouver","Delayed",4.2,0,39.4,"High","Snow",72.1,"High",dt.date(2026,5,6)),
        ("SHP000050","Purolator","Montreal","Calgary","Minor Delay",1.7,0,23.5,"Medium","Rain",77.6,"Medium",dt.date(2026,5,17)),
    ]
    # fmt: on
    rows = [
        Shipment(
            shipment_id=d[0], carrier=d[1], origin=d[2], destination=d[3],
            shipment_status=d[4], delay_hours=d[5], on_time_delivery=d[6],
            route_risk_score=d[7], risk_category=d[8], weather_condition=d[9],
            shipping_cost_cad=d[10], delivery_cost_cad=round(d[10] * 2.54, 2),
            traffic_level=d[11], shipment_date=d[12],
        )
        for d in _D
    ]
    db.add_all(rows)
    db.commit()
    print(f"[seed] inserted {len(rows)} stub shipment rows")


def _seed_stub_incidents(db) -> None:
    """20-row stub covering all 8 incident types and all 4 severity levels."""
    # fmt: off
    # (id, shipment_id, carrier, origin, dest, type, severity, status, delay_h, loss_cad, resolution_h)
    _D = [
        ("INC000001","SHP000007","UPS","Halifax","Calgary","Weather Delay","High","Resolved",5.2,2200.0,84.0),
        ("INC000002","SHP000014","FedEx","Ottawa","Toronto","Mechanical Failure","Medium","Resolved",4.5,1500.0,60.0),
        ("INC000003","SHP000018","FedEx","Edmonton","Vancouver","Traffic Disruption","Critical","Resolved",12.5,2800.0,96.0),
        ("INC000004","SHP000025","DHL","Ottawa","Vancouver","Weather Delay","High","Under Investigation",3.8,2100.0,78.0),
        ("INC000005","SHP000029","DHL","Calgary","Halifax","Failed Delivery Attempt","Low","Resolved",2.7,650.0,24.0),
        ("INC000006","SHP000038","Canada Post","Vancouver","Montreal","Weather Delay","Critical","Resolved",6.1,2900.0,102.0),
        ("INC000007","SHP000046","Purolator","Ottawa","Vancouver","Traffic Disruption","Critical","Under Investigation",11.8,2750.0,92.0),
        ("INC000008","SHP000049","Purolator","Toronto","Vancouver","Damaged Shipment","Medium","Resolved",4.2,1450.0,56.0),
        ("INC000009","SHP000004","UPS","Toronto","Calgary","Failed Delivery Attempt","Low","Resolved",1.5,380.0,18.0),
        ("INC000010","SHP000012","FedEx","Calgary","Vancouver","Weather Delay","Medium","Resolved",1.8,1100.0,48.0),
        ("INC000011","SHP000016","FedEx","Toronto","Edmonton","Customs Hold","Medium","Under Investigation",2.3,1350.0,72.0),
        ("INC000012","SHP000023","DHL","Calgary","Toronto","Damaged Shipment","Low","Resolved",1.2,520.0,28.0),
        ("INC000013","SHP000034","Canada Post","Calgary","Ottawa","Lost Package","High","Open",0,1900.0,0),
        ("INC000014","SHP000043","Purolator","Toronto","Edmonton","Failed Delivery Attempt","Low","Resolved",2.4,290.0,16.0),
        ("INC000015","SHP000050","Purolator","Montreal","Calgary","Customs Hold","Medium","Resolved",1.7,980.0,44.0),
        ("INC000016","SHP000005","UPS","Vancouver","Toronto","Damaged Shipment","Medium","Resolved",2.1,1250.0,52.0),
        ("INC000017","SHP000033","Canada Post","Vancouver","Edmonton","Mechanical Failure","Low","Resolved",0.5,600.0,22.0),
        ("INC000018","SHP000021","DHL","Vancouver","Toronto","Lost Package","High","Under Investigation",0,1750.0,0),
        ("INC000019","SHP000036","Canada Post","Edmonton","Toronto","Warehouse Processing Delay","Low","Resolved",1.0,320.0,14.0),
        ("INC000020","SHP000041","Purolator","Calgary","Toronto","Traffic Disruption","Medium","Resolved",0.8,890.0,36.0),
    ]
    # fmt: on
    stubs = [
        Incident(
            incident_id=d[0], shipment_id=d[1], carrier=d[2], origin=d[3],
            destination=d[4], incident_type=d[5], severity_level=d[6],
            incident_status=d[7], delay_hours=d[8],
            estimated_financial_loss_cad=d[9], resolution_time_hours=d[10],
        )
        for d in _D
    ]
    db.add_all(stubs)
    db.commit()
    print(f"[seed] inserted {len(stubs)} stub incident rows")


def seed() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        current = db.query(Shipment).count()

        # Already have full CSV data — nothing to do.
        if current >= 100:
            print(f"[seed] {current} rows already present — skipping.")
            return

        # Have stub rows (50) but CSV is NOW available — upgrade to full dataset.
        # Have stub rows and CSV is NOT available — keep stubs.
        if current >= 40:
            if not _CSV_AVAILABLE:
                print(f"[seed] {current} stub rows, no CSV found — keeping stubs.")
                return
            # CSV is available: clear stubs and reload from CSV.
            print(f"[seed] {current} stub rows found but CSV is available — upgrading to full CSV load")
            db.query(Shipment).delete()
            db.query(Incident).delete()
            db.commit()

        elif current > 0:
            # Stale legacy rows (< 40) — always clear and reload.
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
