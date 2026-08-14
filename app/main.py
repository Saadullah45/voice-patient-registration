"""FastAPI application: REST endpoints + consistent {data, error} envelope.

Run:  uvicorn app.main:app --reload
Docs: http://localhost:8000/docs
"""
import logging
import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import crud, dashboard, schemas, vapi
from .database import Base, engine, get_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if os.getenv("SEED_ON_STARTUP", "0") == "1":
        from .seed import seed_if_empty
        seed_if_empty()
    yield


app = FastAPI(title="Patient Registration API", version="1.0.0", lifespan=lifespan)
app.include_router(vapi.router)
app.include_router(dashboard.router)


# --- response envelope helpers ---------------------------------------------

def ok(data, code: int = status.HTTP_200_OK):
    return JSONResponse(status_code=code, content={"data": data, "error": None})


def err(message: str, code: int, details=None):
    return JSONResponse(
        status_code=code,
        content={"data": None, "error": {"message": message, "details": details}},
    )


def serialize(patient) -> dict:
    return schemas.PatientOut.model_validate(patient).model_dump(mode="json")


# --- global handlers so even failures use the envelope ----------------------

@app.exception_handler(RequestValidationError)
async def on_validation_error(request: Request, exc: RequestValidationError):
    details = [{"field": e["loc"][-1], "message": e["msg"]} for e in exc.errors()]
    return err("Validation failed", status.HTTP_422_UNPROCESSABLE_ENTITY, details)


@app.exception_handler(Exception)
async def on_unhandled(request: Request, exc: Exception):
    log.exception("unhandled error")
    return err("Internal server error", status.HTTP_500_INTERNAL_SERVER_ERROR)


# --- routes -----------------------------------------------------------------

@app.get("/health")
def health():
    return ok({"status": "ok"})


@app.get("/patients")
def list_patients(
    db: Session = Depends(get_db),
    last_name: str | None = Query(default=None),
    date_of_birth: date | None = Query(default=None, description="YYYY-MM-DD"),
    phone_number: str | None = Query(default=None),
):
    phone = None
    if phone_number:
        try:
            phone = schemas._normalize_phone(phone_number)
        except ValueError:
            return err("Invalid phone_number filter", status.HTTP_400_BAD_REQUEST)
    rows = crud.list_patients(db, last_name=last_name, date_of_birth=date_of_birth, phone_number=phone)
    return ok([serialize(p) for p in rows])


@app.get("/patients/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        return err("Patient not found", status.HTTP_404_NOT_FOUND)
    return ok(serialize(patient))


@app.post("/patients")
def create_patient(payload: schemas.PatientCreate, db: Session = Depends(get_db)):
    existing = crud.get_by_phone(db, payload.phone_number)
    if existing:
        return err(
            "A patient with this phone number already exists",
            status.HTTP_409_CONFLICT,
            {"patient_id": existing.patient_id},
        )
    patient = crud.create_patient(db, payload)
    log.info("created patient %s", patient.patient_id)
    return ok(serialize(patient), code=status.HTTP_201_CREATED)


@app.put("/patients/{patient_id}")
def update_patient(patient_id: str, payload: schemas.PatientUpdate, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        return err("Patient not found", status.HTTP_404_NOT_FOUND)
    patient = crud.update_patient(db, patient, payload)
    return ok(serialize(patient))


@app.delete("/patients/{patient_id}")
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        return err("Patient not found", status.HTTP_404_NOT_FOUND)
    crud.soft_delete(db, patient)
    return ok({"patient_id": patient_id, "deleted": True})
