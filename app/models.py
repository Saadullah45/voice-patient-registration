"""ORM model for a patient record.

Column types/constraints mirror the assessment data model. Soft-delete is
implemented with a nullable `deleted_at`; rows are never physically removed.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Patient(Base):
    __tablename__ = "patients"

    # Stored as a 36-char string so the same schema works on SQLite and Postgres.
    patient_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    date_of_birth: Mapped[Date] = mapped_column(Date, nullable=False)
    sex: Mapped[str] = mapped_column(String(20), nullable=False)

    # Phone numbers are stored normalized to 10 digits for reliable lookup.
    phone_number: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    address_line_1: Mapped[str] = mapped_column(String(200), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)

    insurance_provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    insurance_member_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(50), default="English")

    emergency_contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(10), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# Speeds up the ?last_name= filter.
Index("ix_patients_last_name", Patient.last_name)
