# Voice AI Agent — Patient Registration

A voice agent (Vapi) answers a real U.S. phone number, conversationally collects
patient demographics, confirms them, and persists them through a validated REST
API into a database. Call back later and the data is still there.

```
Caller ─► Vapi (telephony + STT + LLM + TTS) ─► /vapi/webhook ─► CRUD ─► DB
                                                                  ▲
                        REST clients ─► /patients … ──────────────┘
```

The voice webhook and the public REST API share **one validated data layer**, so
the phone path and HTTP path enforce identical rules.

## Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| Telephony + Voice | **Vapi** | Provisions a dialable number and handles STT/TTS/LLM + barge-in/interruptions out of the box, so effort goes into the API the rubric weights most. |
| API | **FastAPI** | Pydantic gives strong server-side validation for free; auto OpenAPI docs at `/docs`. |
| ORM/DB | **SQLAlchemy + SQLite/Postgres** | One `DATABASE_URL` swaps engines. SQLite for zero-setup local dev; Postgres for durable cloud deploys. |
| LLM | Any (set in Vapi) | GPT-4o / Claude both work; prompt is model-agnostic. |

## Project layout
```
app/
  database.py   engine/session (DATABASE_URL: sqlite<->postgres)
  models.py     Patient ORM model + soft-delete column
  schemas.py    Pydantic validation (the authoritative rules)
  crud.py       data-access layer, shared by REST + voice
  vapi.py       /vapi/webhook — translates voice tool-calls to CRUD
  main.py       FastAPI app, routes, {data,error} envelope, handlers
  seed.py       optional demo rows
vapi/
  system_prompt.md   the intake agent's brain (paste into Vapi)
  tools.json         function definitions (paste into Vapi)
tests/test_api.py    pytest integration tests
```

## Setup (local)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # defaults to SQLite; edit if using Postgres
uvicorn app.main:app --reload   # http://localhost:8000/docs
```
Run tests: `pip install -r requirements-dev.txt && PYTHONPATH=. pytest -q`

## Environment variables
| Var | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLite file or Postgres URL | `sqlite:///./patients.db` |
| `VAPI_WEBHOOK_SECRET` | if set, `/vapi/webhook` requires header `X-Vapi-Secret` | *(unset)* |
| `SEED_ON_STARTUP` | insert 2 demo rows when table empty (`1`/`0`) | `0` |

No secrets are hardcoded; the LLM/telephony keys live in Vapi, not this repo.

## Deploy (Render/Railway/Fly)
1. Push to GitHub, create a web service from the repo.
2. Add a **Postgres** instance and set `DATABASE_URL` to it (SQLite on ephemeral
   disk can be wiped on redeploy — see limitations).
3. Start command comes from the `Procfile`:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Note the public URL, e.g. `https://your-app.onrender.com`.

## Wire up the phone
1. In Vapi, create an Assistant. Paste `vapi/system_prompt.md` as the system prompt.
2. Add the three tools from `vapi/tools.json`; set each tool's server URL to
   `https://your-app.onrender.com/vapi/webhook` and add header
   `X-Vapi-Secret: <VAPI_WEBHOOK_SECRET>`.
3. Buy/assign a phone number and attach the assistant. Call it.

## REST API
Envelope on every response: `{ "data": ..., "error": ... }`

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/patients` | filters: `?last_name=`, `?date_of_birth=YYYY-MM-DD`, `?phone_number=` |
| GET | `/patients/:id` | 404 if missing/deleted |
| POST | `/patients` | 201 on create; **409** if phone already exists |
| PUT | `/patients/:id` | partial update |
| DELETE | `/patients/:id` | soft delete (sets `deleted_at`, never hard-deletes) |
| POST | `/vapi/webhook` | voice tool-call bridge (internal) |

Status codes: 200/201 success, 400 bad query, 404 not found, 409 duplicate,
422 validation, 500 unexpected.

Example:
```bash
curl -X POST localhost:8000/patients -H 'Content-Type: application/json' -d '{
  "first_name":"Jane","last_name":"Doe","date_of_birth":"05/14/1990","sex":"Female",
  "phone_number":"(415) 555-0142","address_line_1":"123 Market St",
  "city":"San Francisco","state":"CA","zip_code":"94103"}'
```

## Validation highlights (server-side, not just the agent)
- Names 1–50 chars, letters + hyphen/apostrophe.
- DOB accepts `MM/DD/YYYY` (from voice) or ISO; rejects future / pre-1900 dates.
- Phone normalized to 10 digits (strips formatting, drops leading `1`); area code
  can't start with 0/1. Stored normalized so lookups are reliable.
- State validated against the 50 states + DC; ZIP is 5-digit or ZIP+4.
- `sex` restricted to the four allowed enum values.

## Resilience / edge cases
- Invalid field over the phone → webhook returns a short `validation_failed`
  message naming the field; the agent re-asks just that field (never saves silently).
- Duplicate phone → both REST (409) and voice (`duplicate`) paths refuse to create
  a second record and surface the existing patient.
- DB/unexpected error → wrapped in the `{data,error}` envelope; the webhook never
  throws a 500 back at the voice agent (it returns a speakable error instead).
- Dropped call mid-registration → nothing is written until the caller confirms, so
  a partial call leaves no partial record.

## Known limitations & trade-offs
- **SQLite persistence in the cloud:** fine locally, but on ephemeral-disk hosts a
  redeploy can wipe the file — use Postgres in production (one env var).
- **Phone = identity:** duplicate detection keys on phone number. Two people
  sharing a phone would collide; a real system would use a composite match.
- **Transcripts:** the webhook acknowledges non-tool Vapi events but doesn't yet
  persist full transcripts (hook point is marked in `vapi.py`).
- **AuthN/Z:** REST endpoints are open aside from the webhook secret; production
  would add proper auth and rate limiting. No PHI encryption at rest (out of scope).
- **Appointment scheduling / dashboard:** not built (listed bonuses).

## Observability
Structured stdout logging; every create logs the `patient_id`, and the webhook
logs inbound message types and created patients (satisfies "log the final
collected data payload").
