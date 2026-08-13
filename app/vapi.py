"""Vapi tool-call webhook.

Vapi's LLM calls "tools" (functions) during the call; Vapi POSTs each call to
this endpoint and relays our string result back into the conversation. This is
the voice-agent <-> database bridge, and it reuses the same validated CRUD
layer as the public REST API (single source of truth).

Supported tools:
  - lookup_patient(phone_number)         -> returning-caller / duplicate check
  - create_patient(...all fields...)     -> register a new patient
  - update_patient(patient_id, ...)      -> correct an existing record

Response shape follows Vapi's contract: {"results": [{"toolCallId","result"}]}.
"""
import json
import logging
import os

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import ValidationError

from . import crud, schemas
from .database import SessionLocal

log = logging.getLogger("vapi")
router = APIRouter(prefix="/vapi", tags=["vapi"])

WEBHOOK_SECRET = os.getenv("VAPI_WEBHOOK_SECRET", "")


def _extract_tool_calls(message: dict) -> list[dict]:
    """Normalize the two payload shapes Vapi has used into (id, name, args)."""
    calls = []
    for tc in message.get("toolCallList") or message.get("toolCalls") or []:
        fn = tc.get("function", tc)  # newer shape nests under "function"
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        calls.append({"id": tc.get("id"), "name": fn.get("name"), "args": args})
    return calls


def _handle(name: str, args: dict) -> str:
    """Run one tool call against the DB and return a caller-friendly string."""
    db = SessionLocal()
    try:
        if name == "lookup_patient":
            phone = schemas._normalize_phone(args.get("phone_number", ""))
            existing = crud.get_by_phone(db, phone)
            if existing:
                return json.dumps({
                    "found": True,
                    "patient_id": existing.patient_id,
                    "first_name": existing.first_name,
                    "last_name": existing.last_name,
                })
            return json.dumps({"found": False})

        if name == "create_patient":
            data = schemas.PatientCreate(**args)
            # Duplicate guard: don't create a second row for the same phone.
            dup = crud.get_by_phone(db, data.phone_number)
            if dup:
                return json.dumps({
                    "created": False,
                    "duplicate": True,
                    "patient_id": dup.patient_id,
                    "message": f"A record already exists for {dup.first_name} {dup.last_name}.",
                })
            patient = crud.create_patient(db, data)
            log.info("[vapi] created patient %s (%s %s)",
                     patient.patient_id, patient.first_name, patient.last_name)
            return json.dumps({
                "created": True,
                "patient_id": patient.patient_id,
                "message": f"Registered {patient.first_name} {patient.last_name}.",
            })

        if name == "update_patient":
            patient_id = args.pop("patient_id", None)
            patient = crud.get_patient(db, patient_id) if patient_id else None
            if not patient:
                return json.dumps({"updated": False, "message": "No patient found to update."})
            data = schemas.PatientUpdate(**args)
            crud.update_patient(db, patient, data)
            return json.dumps({"updated": True, "message": "Record updated."})

        return json.dumps({"error": f"Unknown tool '{name}'."})

    except ValidationError as e:
        # Turn Pydantic errors into a short, speakable list of what to re-ask.
        problems = "; ".join(f"{err['loc'][-1]}: {err['msg']}" for err in e.errors())
        return json.dumps({"error": "validation_failed", "message": problems})
    except Exception as e:  # noqa: BLE001 - never 500 the voice agent
        log.exception("[vapi] tool '%s' failed", name)
        return json.dumps({"error": "server_error", "message": str(e)})
    finally:
        db.close()


@router.post("/webhook")
async def vapi_webhook(request: Request, x_vapi_secret: str = Header(default="")):
    if WEBHOOK_SECRET and x_vapi_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="invalid webhook secret")

    body = await request.json()
    message = body.get("message", {})
    log.info("[vapi] inbound message type=%s", message.get("type"))

    calls = _extract_tool_calls(message)
    if not calls:
        # Non-tool events (status-update, end-of-call-report, transcript, etc.)
        # We just acknowledge them; extend here to persist transcripts (bonus).
        return {"results": []}

    results = [{"toolCallId": c["id"], "result": _handle(c["name"], c["args"])} for c in calls]
    return {"results": results}
