"""
Prior authorization.

Two-layer design (same as coding):
  - Whether a procedure needs prior auth is a DETERMINISTIC lookup in
    `payer_rules` — never an LLM guess.
  - The LLM's only job is drafting the clinical justification narrative for a
    staff member to review. The narrative is stored as PENDING_REVIEW and is
    never auto-submitted and never auto-approved (approval is the payer's
    decision, returned as claim/response status).

The prior-auth sub-agent orchestrates: check -> draft -> wait for human
confirm -> submit. The revenue-cycle agent is instructed to block claim
submission when prior auth is required but not yet approved.
"""

import json
import logging
import uuid
from datetime import datetime

from agents import Agent, Runner, function_tool
from config import INTAKE_MODEL, OPENAI_API_KEY
import audit
import database

log = logging.getLogger(__name__)


@function_tool
async def check_prior_auth_required(
    payer: str,
    procedure_code: str,
) -> dict:
    """Determine whether `procedure_code` requires prior authorization for the
    given payer. Deterministic table lookup against payer_rules — never an LLM
    guess. Returns {required: bool, payer, procedure_code, procedure_display,
    notes}."""
    row = await database.query_one(
        """
        SELECT payer_name, procedure_code, procedure_display,
               requires_prior_auth, notes
        FROM payer_rules
        WHERE payer_name = $1 AND procedure_code = $2
        """,
        payer,
        procedure_code,
    )
    if not row:
        return {
            "required": False,
            "payer": payer,
            "procedure_code": procedure_code,
            "procedure_display": None,
            "notes": "no rule on file — treated as not required",
            "resolved_by": "RULE",
        }

    result = {
        "required": bool(row["requires_prior_auth"]),
        "payer": row["payer_name"],
        "procedure_code": row["procedure_code"],
        "procedure_display": row["procedure_display"],
        "notes": row["notes"],
        "resolved_by": "RULE",
    }
    await audit.record(
        actor="check_prior_auth_required",
        action="PRIOR_AUTH_RULE_LOOKUP",
        resource_type="PayerRules",
        summary=f"{payer} {procedure_code} -> requires_prior_auth={result['required']}",
    )
    return result


@function_tool
async def draft_prior_auth_request(
    patient_fhir_id: str,
    payer: str,
    procedure_code: str,
    clinical_note: str,
) -> dict:
    """Draft a prior-authorization request narrative from the patient + note
    using an LLM. Stored as PENDING_REVIEW. This tool never submits and never
    approves — it drafts only, for a human to review and submit."""
    if not clinical_note or not clinical_note.strip():
        raise ValueError("clinical_note is required")

    required = await check_prior_auth_required(payer, procedure_code)
    if not required["required"]:
        return {
            "request_id": None,
            "status": "NOT_REQUIRED",
            "detail": f"prior auth not required for {payer} {procedure_code}",
        }

    narrative = ""
    if OPENAI_API_KEY:
        agent = Agent(
            name="prior_auth_drafter",
            model=INTAKE_MODEL,
            instructions=(
                "You draft a concise clinical justification for a prior "
                "authorization request. Use ONLY facts present in the note. "
                "Do NOT claim anything the note does not support. Output a "
                "single plain-text paragraph, 4-8 sentences, professional and "
                "payer-readable. Never include fabricated diagnoses."
            ),
        )
        result = Runner.run_sync(
            agent,
            f"Patient: {patient_fhir_id}\nProcedure: {procedure_code}\n"
            f"Payer: {payer}\n\nClinical note:\n{clinical_note.strip()[:4000]}",
        )
        narrative = (result.final_output or "").strip()
    else:
        narrative = (
            f"Clinical justification pending manual drafting for "
            f"{procedure_code} ({payer}). OpenAI key not configured."
        )

    request_id = f"PA-{uuid.uuid4().hex[:12].upper()}"
    await database.execute(
        """
        INSERT INTO prior_auth_requests
            (request_id, patient_fhir_id, payer, procedure_code,
             procedure_display, status, narrative, clinical_note)
        VALUES ($1, $2, $3, $4, $5, 'PENDING_REVIEW', $6, $7)
        """,
        request_id,
        patient_fhir_id,
        payer,
        procedure_code,
        required.get("procedure_display"),
        narrative,
        clinical_note,
    )
    await audit.record(
        actor="prior_auth_drafter",
        action="PRIOR_AUTH_DRAFT",
        resource_type="PriorAuthRequest",
        resource_id=request_id,
        summary=f"drafted prior auth {procedure_code} for {payer} (PENDING_REVIEW)",
    )
    return {
        "request_id": request_id,
        "status": "PENDING_REVIEW",
        "narrative": narrative,
        "detail": "Draft only — requires human review before submit.",
    }


@function_tool
async def submit_prior_auth(
    request_id: str,
    approved_by: str = "staff",
) -> dict:
    """Submit a prior-auth request AFTER human review. Moves the request from
    PENDING_REVIEW to SUBMITTED. Approving/denying is the payer's decision —
    tracked on the claim response."""
    row = await database.query_one(
        "SELECT * FROM prior_auth_requests WHERE request_id = $1",
        request_id,
    )
    if not row:
        raise ValueError(f"no prior-auth request with id {request_id}")
    if row["status"] != "PENDING_REVIEW":
        return {
            "request_id": request_id,
            "status": row["status"],
            "detail": f"already {row['status']} — not resubmitted",
        }

    await database.execute(
        "UPDATE prior_auth_requests SET status='SUBMITTED', submitted_at=NOW() WHERE request_id=$1",
        request_id,
    )
    await audit.record(
        actor=approved_by,
        action="PRIOR_AUTH_SUBMIT",
        resource_type="PriorAuthRequest",
        resource_id=request_id,
        summary=f"human-approved submit of {row['procedure_code']} for {row['payer']}",
    )
    return {
        "request_id": request_id,
        "status": "SUBMITTED",
        "procedure_code": row["procedure_code"],
        "payer": row["payer"],
        "detail": "Submitted to payer — approval decision is tracked separately.",
    }


def build_prior_auth_agent(*, model: str | None = None) -> Agent:
    """Sub-agent that checks the rule, drafts after confirming it is required,
    and explicitly stops for human confirmation — never submits on its own."""
    return Agent(
        name="PriorAuthSubAgent",
        model=model or INTAKE_MODEL,
        instructions=(
            "You are the prior-authorization sub-agent. Workflow: "
            "1) call check_prior_auth_required(payer, procedure_code). "
            "2) If required=false, report that no prior auth is needed and "
            "hand back to the main agent. "
            "3) If required=true, call draft_prior_auth_request to produce a "
            "PENDING_REVIEW narrative. "
            "4) STOP — tell the human the draft is ready for review and "
            "DO NOT call submit_prior_auth without explicit human approval. "
            "You never decide approvals; the payer does."
        ),
        tools=[
            check_prior_auth_required,
            draft_prior_auth_request,
            submit_prior_auth,
        ],
    )


async def list_prior_auth_requests(limit: int = 30) -> list[dict]:
    rows = await database.query(
        "SELECT * FROM prior_auth_requests ORDER BY created_at DESC LIMIT $1",
        limit,
    )
    return [
        {
            "id": r["id"],
            "request_id": r["request_id"],
            "patient_fhir_id": r["patient_fhir_id"],
            "payer": r["payer"],
            "procedure_code": r["procedure_code"],
            "procedure_display": r["procedure_display"],
            "status": r["status"],
            "narrative": r["narrative"],
            "created_at": str(r["created_at"]),
            "submitted_at": str(r["submitted_at"]) if r["submitted_at"] else None,
        }
        for r in rows
    ]