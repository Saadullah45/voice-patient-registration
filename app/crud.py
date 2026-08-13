"""Thin data-access layer. Keeps SQLAlchemy out of the route handlers so the
same functions are reusable by both the REST routes and the Vapi webhook.
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas


def _active(stmt):
    """Restrict a query to non-soft-deleted rows."""
    return stmt.where(models.Patient.deleted_at.is_(None))


def list_patients(
    db: Session,
    last_name: Optional[str] = None,
    date_of_birth: Optional[date] = None,
    phone_number: Optional[str] = None,
):
    stmt = _active(select(models.Patient))
    if last_name:
        stmt = stmt.where(models.Patient.last_name.ilike(last_name))
    if date_of_birth:
        stmt = stmt.where(models.Patient.date_of_birth == date_of_birth)
    if phone_number:
        stmt = stmt.where(models.Patient.phone_number == phone_number)
    return db.execute(stmt.order_by(models.Patient.created_at.desc())).scalars().all()


def get_patient(db: Session, patient_id: str) -> Optional[models.Patient]:
    stmt = _active(select(models.Patient).where(models.Patient.patient_id == patient_id))
    return db.execute(stmt).scalar_one_or_none()


def get_by_phone(db: Session, phone_number: str) -> Optional[models.Patient]:
    """Used for duplicate / returning-caller detection."""
    stmt = _active(select(models.Patient).where(models.Patient.phone_number == phone_number))
    return db.execute(stmt).scalars().first()


def create_patient(db: Session, data: schemas.PatientCreate) -> models.Patient:
    patient = models.Patient(**data.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def update_patient(
    db: Session, patient: models.Patient, data: schemas.PatientUpdate
) -> models.Patient:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return patient


def soft_delete(db: Session, patient: models.Patient) -> models.Patient:
    patient.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(patient)
    return patient
