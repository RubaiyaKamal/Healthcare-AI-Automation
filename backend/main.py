"""
FastAPI backend for Healthcare AI — Phase 1.

REST surface the Next.js frontend talks to:
  GET  /api/patients                 — list from cache
  GET  /api/patients/{fhir_id}       — get_patient (cache-first)
  POST /api/patients/intake          — run intake agent over a message history
  POST /api/eligibility/check        — deterministic eligibility check
  GET  /api/eligibility/{fhir_id}    — recent checks for a patient
  GET  /api/audit                    — recent audit rows
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import audit
import database
import eligibility
import intake_agent
import patient_lookup
from registration import PatientInput as PatientForm

logging.basicConfig(level=logging.INFO)

from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_pool()
    yield
    await database.close_pool()


app = FastAPI(title="Healthcare AI — Phase 1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# Schemas
# ------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class IntakeRequest(BaseModel):
    messages: list[ChatMessage]
    actor: str = "frontend"


class IntakeResponse(BaseModel):
    output: str
    tool_calls: list[dict] = Field(default_factory=list)
    trace_id: str = ""


class EligibilityRequest(BaseModel):
    patient_fhir_id: str
    actor: str = "frontend"


# ------------------------------------------------------------
# Patients
# ------------------------------------------------------------
@app.get("/api/patients")
async def list_patients():
    rows = await database.query(
        """
        SELECT fhir_id, first_name, last_name, dob, gender, mrn, insurer, member_id
        FROM patients
        ORDER BY last_name, first_name
        LIMIT 200
        """
    )
    return [dict(r) for r in rows]


@app.get("/api/patients/{fhir_id}")
async def get_patient(fhir_id: str):
    patient = await patient_lookup.get_patient(fhir_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.post("/api/patients")
async def create_patient(form: PatientForm):
    """Deterministic (non-agent) registration path — used when the UI wants a
    plain form POST instead of the agent chat. STILL enforces duplicate check."""
    import registration

    dup = await _dup_check(form)
    if dup["is_duplicate"]:
        raise HTTPException(status_code=409, detail=dup)

    result = await registration.register_patient(form.model_dump())
    return result


async def _dup_check(form: PatientForm):
    from duplicate_check import check_for_duplicates
    return await check_for_duplicates(
        form.first_name, form.last_name, form.dob, ai_judge=True
    )


# ------------------------------------------------------------
# Intake agent
# ------------------------------------------------------------
@app.post("/api/intake", response_model=IntakeResponse)
async def intake(req: IntakeRequest):
    await audit.record(
        actor=req.actor,
        action="AGENT_INTAKE",
        summary=f"intake chat: {len(req.messages)} messages",
    )
    return await _run_intake_async(req.messages)


async def _run_intake_async(messages):
    # Run the agent in a threadpool — Runner.run_sync is blocking.
    import asyncio
    return await asyncio.to_thread(intake_agent.run_intake_sync, [m.model_dump() for m in messages])


# ------------------------------------------------------------
# Eligibility
# ------------------------------------------------------------
@app.post("/api/eligibility/check")
async def eligibility_check(req: EligibilityRequest):
    result = await eligibility.check_eligibility(
        patient_fhir_id=req.patient_fhir_id,
        actor=req.actor,
    )
    return result


@app.get("/api/eligibility/{fhir_id}")
async def eligibility_history(fhir_id: str):
    rows = await database.query(
        """
        SELECT id, status, payer, member_id, resolved_by, checked_at
        FROM eligibility_checks
        WHERE patient_fhir_id = $1
        ORDER BY checked_at DESC
        LIMIT 20
        """,
        fhir_id,
    )
    return [dict(r) for r in rows]


# ------------------------------------------------------------
# Audit
# ------------------------------------------------------------
@app.get("/api/audit")
async def audit_log(limit: int = 50):
    rows = await database.query(
        """
        SELECT actor, actor_type, action, resource_type, resource_id, summary, created_at
        FROM audit_log
        ORDER BY created_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)