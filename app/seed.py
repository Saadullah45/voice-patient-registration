"""Insert 1-2 demo patients when the table is empty (opt-in via SEED_ON_STARTUP)."""
from sqlalchemy import select

from . import models
from .database import SessionLocal


SEED = [
    dict(
        first_name="Jane", last_name="Doe", date_of_birth=__import__("datetime").date(1990, 5, 14),
        sex="Female", phone_number="4155550142", email="jane.doe@example.com",
        address_line_1="123 Market St", city="San Francisco", state="CA", zip_code="94103",
        insurance_provider="Blue Shield", insurance_member_id="BS123456789",
        preferred_language="English",
    ),
    dict(
        first_name="Carlos", last_name="Ramirez", date_of_birth=__import__("datetime").date(1985, 11, 2),
        sex="Male", phone_number="3105550199", address_line_1="88 Sunset Blvd",
        city="Los Angeles", state="CA", zip_code="90028", preferred_language="Spanish",
    ),
]


def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        exists = db.execute(select(models.Patient.patient_id).limit(1)).first()
        if exists:
            return
        for row in SEED:
            db.add(models.Patient(**row))
        db.commit()
        print(f"[seed] inserted {len(SEED)} demo patients")
    finally:
        db.close()
