"""API integration tests (bonus). Run: pytest -q

Uses an isolated temp SQLite DB so it never touches dev/prod data.
"""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["SEED_ON_STARTUP"] = "0"

from fastapi.testclient import TestClient  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)

VALID = {
    "first_name": "Test", "last_name": "Patient", "date_of_birth": "01/15/1990",
    "sex": "Male", "phone_number": "(415) 555-0111", "address_line_1": "1 Main St",
    "city": "Reno", "state": "nv", "zip_code": "89501",
}


def test_create_and_normalize():
    r = client.post("/patients", json=VALID)
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["phone_number"] == "4155550111"  # stripped/normalized
    assert data["state"] == "NV"                  # upper-cased
    assert data["date_of_birth"] == "1990-01-15"  # MM/DD/YYYY -> ISO


def test_rejects_future_dob_and_bad_phone():
    bad = {**VALID, "phone_number": "123", "date_of_birth": "01/01/2999"}
    r = client.post("/patients", json=bad)
    assert r.status_code == 422
    fields = {d["field"] for d in r.json()["error"]["details"]}
    assert {"phone_number", "date_of_birth"} <= fields


def test_duplicate_phone_conflicts():
    body = {**VALID, "phone_number": "4155550222"}
    assert client.post("/patients", json=body).status_code == 201
    assert client.post("/patients", json=body).status_code == 409


def test_get_update_softdelete_lifecycle():
    body = {**VALID, "phone_number": "4155550333"}
    pid = client.post("/patients", json=body).json()["data"]["patient_id"]

    assert client.get(f"/patients/{pid}").status_code == 200

    r = client.put(f"/patients/{pid}", json={"last_name": "Renamed"})
    assert r.json()["data"]["last_name"] == "Renamed"

    assert client.delete(f"/patients/{pid}").status_code == 200
    assert client.get(f"/patients/{pid}").status_code == 404  # hidden after soft delete


def test_missing_patient_404():
    assert client.get("/patients/does-not-exist").status_code == 404


def test_vapi_lookup_and_create():
    body = {"message": {"type": "tool-calls", "toolCallList": [
        {"id": "t1", "name": "create_patient", "arguments": {**VALID, "phone_number": "4155550444"}}
    ]}}
    r = client.post("/vapi/webhook", json=body)
    assert r.status_code == 200
    assert '"created": true' in r.json()["results"][0]["result"]

    look = {"message": {"type": "tool-calls", "toolCallList": [
        {"id": "t2", "name": "lookup_patient", "arguments": {"phone_number": "4155550444"}}
    ]}}
    assert '"found": true' in client.post("/vapi/webhook", json=look).json()["results"][0]["result"]
