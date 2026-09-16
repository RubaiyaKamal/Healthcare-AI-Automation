"""
FastAPI backend for HealthFlow AI — Phase 1 & 2.

REST surface the Next.js frontend talks to:
  GET  /api/patients                 — list from cache
  GET  /api/patients/{fhir_id}       — get_patient (cache-first)
  POST /api/patients/intake          — run intake agent over a message history
  POST /api/eligibility/check        — deterministic eligibility check
  GET  /api/eligibility/{fhir_id}    — recent checks for a patient
  GET  /api/rcm/coding               — recent coding suggestions
  POST /api/rcm/run                  — full revenue cycle agent
  GET  /api/rcm/claims               — claim funnel list
  GET  /api/rcm/denials              — denial queue
  GET  /api/rcm/prior-auth           — prior auth requests
  GET  /api/rcm/metrics              — funnel metrics
  POST /api/rcm/suggest-denial-fix   — trigger LLM denial fix suggestion
  POST /api/chat/site                — site visitor (marketing) chatbot turn
  POST /api/chat/site/demo-request   — capture a demo/sales lead
  POST /api/chat/portal              — patient portal chatbot turn (scoped)
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


app = FastAPI(title="HealthFlow AI", lifespan=lifespan)

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
# Revenue Cycle (Phase 2)
# ------------------------------------------------------------
class RCMRunRequest(BaseModel):
    patient_fhir_id: str
    clinical_note: str
    payer: str = ""
    actor: str = "frontend"


class DenialFixRequest(BaseModel):
    denial_id: int


@app.get("/api/rcm/coding")
async def coding_suggestions(limit: int = 30):
    from rcm_coding import list_coding_suggestions
    return await list_coding_suggestions(limit=limit)


@app.post("/api/rcm/run", response_model=IntakeResponse)
async def rcm_run(req: RCMRunRequest):
    import asyncio
    import rcm_agent

    await audit.record(
        actor=req.actor,
        action="AGENT_RCM_RUN",
        summary=f"revenue cycle: patient={req.patient_fhir_id}",
    )
    return await asyncio.to_thread(
        rcm_agent.run_revenue_cycle_sync,
        {
            "patient_fhir_id": req.patient_fhir_id,
            "clinical_note": req.clinical_note,
            "payer": req.payer,
        },
    )


@app.get("/api/rcm/claims")
async def rcm_claims(limit: int = 50):
    from rcm_claims import list_claims
    return await list_claims(limit=limit)


@app.get("/api/rcm/denials")
async def rcm_denials(limit: int = 30):
    from rcm_denials import list_denials
    return await list_denials(limit=limit)


@app.get("/api/rcm/prior-auth")
async def rcm_prior_auth(limit: int = 30):
    from rcm_prior_auth import list_prior_auth_requests
    return await list_prior_auth_requests(limit=limit)


@app.get("/api/rcm/metrics")
async def rcm_metrics():
    """Claim funnel + denial metrics for the dashboard."""
    total, paid, denied, partial, pending, error, open_denials = (
        0, 0, 0, 0, 0, 0, 0
    )
    async with database.get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*)                     AS total,
                   COALESCE(SUM((status='PAID')::int), 0) AS paid,
                   COALESCE(SUM((status='DENIED')::int), 0) AS denied,
                   COALESCE(SUM((status='PARTIALLY_PAID')::int), 0) AS partial,
                   COALESCE(SUM((status='SUBMITTED')::int) + SUM((status='PENDING')::int), 0) AS pending,
                   COALESCE(SUM((status='ERROR')::int), 0) AS error
            FROM claims
            """
        )
        total = row["total"] or 0
        paid = row["paid"] or 0
        denied = row["denied"] or 0
        partial = row["partial"] or 0
        pending = row["pending"] or 0
        error = row["error"] or 0
        drow = await conn.fetchval(
            "SELECT COUNT(*) FROM denials WHERE fix_status = 'OPEN'"
        )
        open_denials = drow or 0
    return {
        "funnel": {
            "total": total,
            "paid": paid,
            "denied": denied,
            "partially_paid": partial,
            "pending": pending,
            "error": error,
        },
        "open_denials": open_denials,
        "denial_rate": round(denied / total * 100, 1) if total else 0.0,
    }


@app.post("/api/rcm/suggest-denial-fix")
async def suggest_denial_fix(req: DenialFixRequest):
    from rcm_denials import suggest_denial_fix
    return await suggest_denial_fix(req.denial_id)


# ------------------------------------------------------------
# Chatbots (Phase 3)
# ------------------------------------------------------------
class SiteChatMessage(BaseModel):
    message: str


class DemoRequestForm(BaseModel):
    name: str
    email: str
    hospital: str
    message: str = ""


def _parse_jsonb_list(value) -> list:
    """asyncpg returns jsonb as text by default (no codec is registered for it),
    so normalize to a real list before appending/returning."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            import json
            return json.loads(value)
        except Exception:
            return []
    return list(value)


class PortalChatMessage(BaseModel):
    session_id: str = ""
    patient_fhir_id: str
    message: str


@app.post("/api/chat/site")
async def site_chat(req: SiteChatMessage):
    """Site visitor (marketing) chatbot — deterministic, scoped to pre-sales."""
    import site_chatbot

    if not (req.message or "").strip():
        return {
            "reply": site_chatbot.INTRO_REPLY,
            "kind": "intro",
            "quick_replies": site_chatbot.INTRO_REPLIES,
            "wants_demo": False,
        }
    await audit.record(
        actor="site_chatbot",
        action="SITE_CHAT_TURN",
        summary=f"site chat: {req.message.strip()[:120]}",
        actor_type="tool",
    )
    return site_chatbot.respond(req.message)


@app.post("/api/chat/site/demo-request")
async def site_demo_request(req: DemoRequestForm):
    """Book-a-demo lead capture — stores a sales lead the team can follow up on."""
    import site_chatbot

    result = await site_chatbot.store_demo_request(
        req.name, req.email, req.hospital, req.message
    )
    return result


@app.post("/api/chat/portal")
async def portal_chat(req: PortalChatMessage):
    """Patient portal chatbot turn. Sessions persist to chat_sessions so every
    exchange is logged like the rest of the patient record."""
    import json
    import uuid
    import patient_chatbot

    patient_fhir_id = (req.patient_fhir_id or "").strip()
    if not patient_fhir_id:
        raise HTTPException(status_code=422, detail="patient_fhir_id is required")

    session_id = req.session_id.strip()

    if session_id:
        row = await database.query_one(
            """
            SELECT session_id, patient_fhir_id, phase, messages
            FROM chat_sessions
            WHERE session_id = $1 AND bot = 'portal'
            """,
            session_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        # A session is bound to one patient — never swap records mid-chat.
        if row["patient_fhir_id"] != patient_fhir_id:
            raise HTTPException(status_code=409, detail="Session belongs to another patient")
        messages = _parse_jsonb_list(row.get("messages"))
        phase = row["phase"] or "open"
    else:
        session_id = f"PORTAL-{uuid.uuid4().hex[:10].upper()}"
        messages = []
        phase = "open"
        await database.execute(
            """
            INSERT INTO chat_sessions (session_id, bot, patient_fhir_id, phase, messages)
            VALUES ($1, 'portal', $2, 'open', '[]'::jsonb)
            """,
            session_id, patient_fhir_id,
        )

    response = await patient_chatbot.handle_message(
        session_id=session_id,
        patient_fhir_id=patient_fhir_id,
        phase=phase,
        message=req.message,
    )

    messages.append({"role": "user", "content": req.message})
    messages.append({
        "role": "assistant",
        "content": response["reply"],
        "kind": response["kind"],
        "phase": response["phase"],
        "hard_stop": response.get("hard_stop", False),
    })
    await database.execute(
        """
        UPDATE chat_sessions
        SET phase = $3, messages = $4::jsonb, updated_at = NOW()
        WHERE session_id = $1
        """,
        session_id, patient_fhir_id, response["phase"], json.dumps(messages),
    )

    await audit.record(
        actor="patient_portal_chatbot",
        action="PORTAL_CHAT_TURN",
        resource_type="ChatSession",
        resource_id=session_id,
        summary=f"portal chat: kind={response['kind']} phase={response['phase']}",
        actor_type="tool",
    )

    return {
        "session_id": session_id,
        "reply": response["reply"],
        "quick_replies": response.get("quick_replies", []),
        "kind": response.get("kind", "info"),
        "phase": response.get("phase", "open"),
        "hard_stop": response.get("hard_stop", False),
        "data": response.get("data", {}),
    }


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