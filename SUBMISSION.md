# CareCloud Take-Home Submission — Voice AI Agent (Patient Registration)

**Candidate:** Saad Ullah Bilal
**Position:** AI Engineer

## Links

| | |
|---|---|
| **Repository** | https://github.com/Saadullah45/voice-patient-registration |
| **US phone number to call** | +1 (959) 251-0335 |
| **API base URL** | https://voice-patient-registration-2gat.onrender.com |
| **Interactive API docs (Swagger)** | https://voice-patient-registration-2gat.onrender.com/docs |
| **Dashboard** (read-only patient list) | https://voice-patient-registration-2gat.onrender.com/dashboard |

## Notes for testing

- No credentials are needed to test — the phone number is live and the REST API (`/patients`, `/dashboard`) is open, matching the assessment's "basic input sanitization, no hardcoded secrets" bar rather than full production auth (documented as a known limitation in the README).
- Call the number and register as a new patient in natural conversation. The agent (Riley) will greet you, ask for your phone number first (to check for an existing record), then collect the required demographics, offer optional fields, read everything back for confirmation, and save.
- Call back on the same number afterward — the agent will recognize your phone number as a returning caller and offer to update your record instead of registering a duplicate.
- The service runs on Render's free tier and is kept warm by an uptime monitor pinging `/health` every 5 minutes, so there should be no cold-start delay when you call.
- Two demo patients (Jane Doe, Carlos Ramirez) are seeded for convenience — visible via `/dashboard` or `GET /patients`.
- Full architecture, tech-stack rationale, environment variables, validation rules, and known limitations/trade-offs are documented in [`README.md`](./README.md) in the repository.

## Quick verification without calling

```bash
curl https://voice-patient-registration-2gat.onrender.com/health
curl https://voice-patient-registration-2gat.onrender.com/patients
```
