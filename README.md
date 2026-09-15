# HealthFlow AI — Phase 1

FHIR-backed agentic automations: patient intake and insurance eligibility.

## Architecture

```
Next.js (Dashboard)  ── REST ──►  FastAPI (Python)
                                    └─ OpenAI Agents SDK
                                        ├─ Intake Agent (chat, duplicate-guardrail)
                                        └─ Eligibility classifier (rules-first)
                                    Tools
                                        ├─ fhir_client.py    → local HAPI FHIR
                                        ├─ patient_lookup.py → get_patient/search
                                        ├─ duplicate_check.py
                                        ├─ registration.py
                                        └─ eligibility.py
                                    PostgreSQL (app-db)
                                        ├─ patients (cache), encounters
                                        ├─ audit_log, eligibility_checks,
                                        ├─ sessions, duplicate_check_log
```

## Prerequisites

- Docker + Docker Compose
- Python 3.10+ (backend)
- Node 20+ (frontend)
- `OPENAI_API_KEY` in `.env` (needed for the intake agent; eligibility works
  rules-first even without it)

## Quick start

```bash
# 1. Infrastructure — local HAPI FHIR + app-db (Postgres)
cp .env.example .env           # then put your real OPENAI_API_KEY in
docker compose up -d --build

# 2. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (or: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 3. Seed synthetic patients (with Coverage resources)
python seed_synthea_data.py --count 12

# 4. Frontend
cd ../frontend
npm install
npm run dev                     # http://localhost:3000

# 5. Tests (backend pure logic)
cd ../backend
python -m pytest tests/ -q
```

## Endpoints (backend)

| Method | Path                        | Purpose                                  |
|--------|-----------------------------|------------------------------------------|
| GET    | `/api/patients`             | List cached patients                     |
| GET    | `/api/patients/{id}`        | get_patient (cache-first + FHIR refresh) |
| POST   | `/api/patients`             | Deterministic registration (dup-checked) |
| POST   | `/api/intake`               | Intake agent chat                        |
| POST   | `/api/eligibility/check`    | Eligibility check (rules-first)          |
| GET    | `/api/eligibility/{id}`     | Historical checks for a patient          |
| GET    | `/api/audit`                | Recent audit trail rows                  |

## Demo pages

- `/intake` — agent chat. Try: _"Register a new patient: Maria Lopez, DOB 1985-04-12, phone 555-0102"_
  Watch the tool-call transcript: `validate_patient_data` → `check_for_duplicates` → `register_patient`.
- `/eligibility` — pick a patient, click Check Eligibility, see the live result
  plus `resolved_by: RULE|LLM` and the audit trail.

## Mobile app (Expo)

Companion React Native app in `mobile/` with the same Home / Intake / Eligibility
flows. Run it with Expo Go:

```bash
cd mobile
npx expo start        # scan the QR in Expo Go
```

The API base URL is derived from the Expo dev-server host automatically, so the
phone reaches the FastAPI backend on your machine. Start the backend bound to
all interfaces if the phone is not on the same host:

```bash
cd backend
.venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## Design notes

- **Duplicate safety**: exact SQL match → pg_trgm fuzzy candidates → LLM only
  judges borderline cases. The agent never auto-merges; it flags and asks.
- **Rules-first eligibility**: deterministic classifier; `gpt-4o-mini` runs only
  for unrecognized Coverage shapes. Every result records `resolved_by`.
- **Audit trail**: every tool writes to `audit_log` (actor, action, resource, when).
- **Local-only data**: HAPI FHIR runs in Docker; no dependency on hapi.fhir.org.
- **Not HIPAA-ready**: sandbox infra, no authN/authZ yet. Do not load real PHI.

## Phase 1 scope (done)

1. EHR core: FHIR client, Synthea-style seeder, Postgres cache, get_patient, audit.
2. Intake: registration form + `register_patient` tool + duplicate check + Intake Agent.
3. Eligibility: `check_eligibility` tool (rules→LLM), response parser, stored result, demo UI.