"""
Creates all tables and inserts sample shipment rows so the SQL Agent has
something real to query out of the box (`python -m app.db.seed`).
"""
import datetime as dt
import random

from app.db.models import Base, OperationsData
from app.db.session import SessionLocal, engine

CITIES = ["Toronto", "Vancouver", "Calgary", "Montreal", "New York", "Chicago", "Seattle"]
STATUSES = ["delayed", "on_time", "on_time", "cancelled"]  # weighted toward on_time


def seed() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.query(OperationsData).count() > 0:
            print("operations_data already seeded, skipping.")
            return

        today = dt.date.today()
        rows = []
        for i in range(120):
            origin, destination = random.sample(CITIES, 2)
            status = random.choice(STATUSES)
            delay_days = random.randint(1, 7) if status == "delayed" else 0
            shipped_at = today - dt.timedelta(days=random.randint(0, 60))
            rows.append(
                OperationsData(
                    origin=origin,
                    destination=destination,
                    status=status,
                    delay_days=delay_days,
                    shipped_at=shipped_at,
                )
            )
        db.add_all(rows)
        db.commit()
        print(f"Seeded {len(rows)} operations_data rows.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
