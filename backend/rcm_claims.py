"""
Medical billing & claims.

  build_claim          -> assemble a FHIR Claim from patient + validated codes
  submit_claim         -> POST to clearinghouse (simulated), record SUBMITTED
  parse_claim_response -> rule-first classifier -> PAID/DENIED/PARTIALLY_PAID/PENDING
  check_claim_status   -> current claim state for the dashboard
  resubmit_claim       -> re-submit after a denial fix (human-approved)

Same pattern as eligibility.py: deterministic rules classify the ClaimResponse
outcome first; an LLM fallback runs only for unrecognized response shapes.
The FHIR Claim/ClaimResponse is the source of truth; the `claims` table is
state/cache/audit only.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from agents import function_tool
import audit
import database
from config import ELIGIBILITY_MODEL, OPENAI_API_KEY

log = logging.getLogger(__name__)

CLAIM_STATUSES = (
    "DRAFT", "SUBMITTED", "PENDING", "PAID", "PARTIALLY_PAID", "DENIED", "ERROR"
)

# Simulated clearinghouse fixed-ish distribution (per claim).
SIM_OUTCOMES = ("complete", "complete", "complete", "error", "queued")


# ------------------------------------------------------------
# Pure: assemble a FHIR Claim (no I/O)
# ------------------------------------------------------------
def assemble_claim(
    patient_fhir_id: str,
    codes: list[dict],
    payer: str | None = None,
    encounter_fhir_id: str | None = None,
    total_amount: float | None = None,
) -> dict:
    """Build a FHIR R4 Claim resource from validated codes. Pure function so it
    can be unit-tested without FHIR/DB."""
    item = []
    for i, c in enumerate(codes, start=1):
        system = c.get("system", "CPT")
        code = c.get("code", "")
        item.append({
            "sequence": i,
            "productOrService": {
                "coding": [{
                    "system": f"http://hl7.org/fhir/sid/{system.lower()}",
                    "code": code,
                    "display": c.get("display") or c.get("summary"),
                }],
            },
        })

    claim = {
        "resourceType": "Claim",
        "status": "active",
        "type": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/claim-type", "code": "professional"}],
        },
        "use": "claim",
        "patient": {"reference": f"Patient/{patient_fhir_id}"},
        "created": datetime.now(timezone.utc).date().isoformat(),
        "provider": {"display": "HealthFlow Demo Clinic"},
        "priority": {"coding": [{"code": "normal"}]},
        "item": item,
    }
    if payer:
        claim["insurer"] = {"display": payer}
    if encounter_fhir_id:
        claim["encounter"] = [{"reference": f"Encounter/{encounter_fhir_id}"}]
    if total_amount is not None:
        claim["total"] = {"value": float(total_amount), "currency": "USD"}
    return claim


def _pick_claim_id() -> str:
    return f"CLM-{uuid.uuid4().hex[:12].upper()}"


# ------------------------------------------------------------
# Deterministic simulated clearinghouse response
# ------------------------------------------------------------
def simulate_claim_response(claim_id: str) -> dict:
    """Simulated ClaimResponse from the clearinghouse. Deterministic per
    claim_id so demos are reproducible (no real payer API in the sandbox)."""
    import hashlib

    h = int(hashlib.sha256(claim_id.encode()).hexdigest()[:8], 16)
    r = (h % 10)
    if r < 5:
        outcome, disposition = "complete", "Paid in full"
    elif r < 7:
        outcome, disposition = "complete", "Partially paid — line item reduced"
    elif r < 9:
        outcome, disposition = "complete", "Denied - service not covered"
    else:
        outcome, disposition = "queued", "Pending review"

    response = {
        "resourceType": "ClaimResponse",
        "status": "active",
        "outcome": outcome,
        "disposition": disposition,
        "created": datetime.now(timezone.utc).date().isoformat(),
        "request": {"reference": f"Claim/{claim_id}"},
    }
    if outcome == "complete" and disposition.startswith("Paid in full"):
        response["payment"] = {"amount": {"value": 250.0, "currency": "USD"}}
    elif outcome == "complete" and disposition.startswith("Partially"):
        response["payment"] = {"amount": {"value": 150.0, "currency": "USD"}}
    if disposition.startswith(("Paid", "Partially")):
        response["total"] = {"value": 0, "currency": "USD"}
    return response


# ------------------------------------------------------------
# Pure: rule-first classifier (identical shape to eligibility._rule_based)
# ------------------------------------------------------------
def _rule_based_claim_response(resp: dict) -> dict:
    """Map a ClaimResponse to a local claim status with RULE first."""
    outcome = (resp.get("outcome") or "").lower()
    disposition = (resp.get("disposition") or "").lower()
    status = (resp.get("status") or "").lower()

    if status in ("cancelled", "entered-in-error"):
        return {"status": "ERROR", "detail": f"response status='{status}'"}

    if outcome == "queued" or outcome in ("pending", "processing"):
        return {"status": "PENDING", "detail": disposition or "response queued"}

    if outcome == "error":
        return {"status": "ERROR", "detail": disposition or "response error"}

    if outcome == "complete":
        if any(k in disposition for k in ("denied", "denial", "rejected", "not covered")):
            return {"status": "DENIED", "detail": disposition or "denied"}
        if any(k in disposition for k in ("partial", "reduced", "adjusted")):
            return {"status": "PARTIALLY_PAID", "detail": disposition or "partially paid"}
        if any(k in disposition for k in ("paid", "approved", "accepted", "adjudicated")):
            return {"status": "PAID", "detail": disposition or "paid"}
        return {"status": "PENDING", "detail": disposition or "complete but unrecognized disposition"}

    return {"status": "UNRECOGNIZED", "detail": f"unrecognized outcome='{outcome}'"}


def _llm_fallback_claim_response(resp: dict) -> dict:
    """Only invoked for UNRECOGNIZED response shapes. Cheap, bounded, audited."""
    from agents import Agent, Runner

    if not OPENAI_API_KEY:
        return {"status": "PENDING", "detail": "could not classify; LLM fallback disabled"}

    agent = Agent(
        name="claim_response_classifier",
        model=ELIGIBILITY_MODEL,
        instructions=(
            "You classify an insurance ClaimResponse. Output exactly one JSON "
            'object: {"status": "PAID"|"DENIED"|"PARTIALLY_PAID"|"PENDING"|"ERROR", '
            '"detail": "<one line>"}. PAID=accepted; DENIED=rejected; '
            "PARTIALLY_PAID=partial; PENDING=in progress; ERROR=malformed."
        ),
    )
    result = Runner.run_sync(agent, f"ClaimResponse: {json.dumps(resp)[:1500]}")
    try:
        return json.loads(result.final_output or "{}")
    except Exception:
        log.warning("LLM claim classifier returned non-JSON: %r", (result.final_output or "")[:120])
        return {"status": "PENDING", "detail": "LLM output unparseable"}


@function_tool(strict_mode=False)
async def parse_claim_response(claim_response: dict) -> dict:
    """Rule-first classifier for a ClaimResponse resource. Maps outcome to
    PAID | DENIED | PARTIALLY_PAID | PENDING | ERROR. LLM runs only for
    unrecognized shapes. Returns {status, detail, resolved_by}."""
    result = _rule_based_claim_response(claim_response)
    resolved_by = "RULE"
    if result["status"] == "UNRECOGNIZED":
        llm = _llm_fallback_claim_response(claim_response)
        result.update(llm)
        resolved_by = "LLM"
    result["resolved_by"] = resolved_by
    return result


# ------------------------------------------------------------
# Claim lifecycle (I/O)
# ------------------------------------------------------------
@function_tool(strict_mode=False)
async def build_claim(
    patient_fhir_id: str,
    codes: list[dict],
    payer: str | None = None,
    encounter_fhir_id: str | None = None,
    total_amount: float | None = None,
) -> dict:
    """Assemble a FHIR Claim from a patient and a list of VALIDATED codes
    ({system, code, display?}). Creates the Claim in the local FHIR server
    (source of truth) and records a DRAFT in the claims table. Always call
    validate_codes before build_claim."""
    from fhir_client import get_client, FHIRValidationError

    if not patient_fhir_id or not codes:
        raise ValueError("patient_fhir_id and codes are required")

    claim_resource = assemble_claim(
        patient_fhir_id, codes, payer, encounter_fhir_id, total_amount
    )

    created = None
    try:
        created = get_client().create(claim_resource)
    except FHIRValidationError as e:
        log.warning("FHIR rejected Claim: %s", e)
        created = claim_resource  # degrade gracefully in sandbox

    claim_id = _pick_claim_id()
    await database.execute(
        """
        INSERT INTO claims (claim_id, patient_fhir_id, encounter_fhir_id, payer,
                            total_amount, codes, status, raw_claim)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, 'DRAFT', $7::jsonb)
        """,
        claim_id,
        patient_fhir_id,
        encounter_fhir_id,
        payer,
        total_amount,
        json.dumps([{k: c.get(k) for k in ("system", "code", "display", "summary")} for c in codes]),
        json.dumps(created or claim_resource),
    )
    await audit.record(
        actor="build_claim",
        action="BUILD_CLAIM",
        resource_type="Claim",
        resource_id=claim_id,
        summary=f"built claim for patient={patient_fhir_id} with {len(codes)} codes",
    )
    return {
        "claim_id": claim_id,
        "patient_fhir_id": patient_fhir_id,
        "status": "DRAFT",
        "codes": [{"system": c.get("system"), "code": c.get("code")} for c in codes],
    }


@function_tool
async def submit_claim(claim_id: str) -> dict:
    """Submit a built claim to the clearinghouse (simulated locally). Records a
    response via parse_claim_response and updates claim state. Returns the
    final {claim_id, status, detail, resolved_by, response}."""
    row = await database.query_one("SELECT * FROM claims WHERE claim_id = $1", claim_id)
    if not row:
        raise ValueError(f"no claim with id {claim_id}")

    await database.execute(
        "UPDATE claims SET status='SUBMITTED', updated_at=NOW() WHERE claim_id=$1",
        claim_id,
    )

    response = simulate_claim_response(claim_id)
    parsed = await parse_claim_response(response)

    # Try to persist the ClaimResponse in FHIR (best-effort; sandbox may not have FHIR).
    try:
        from fhir_client import get_client
        get_client().create(response)
    except Exception as e:
        log.info("ClaimResponse FHIR write skipped: %s", e)

    await database.execute(
        """
        UPDATE claims SET status=$2, claim_response=$3::jsonb, resolved_by=$4, updated_at=NOW()
        WHERE claim_id=$1
        """,
        claim_id,
        parsed["status"],
        json.dumps(response),
        parsed.get("resolved_by", "RULE"),
    )
    await audit.record(
        actor="submit_claim",
        action="SUBMIT_CLAIM",
        resource_type="Claim",
        resource_id=claim_id,
        summary=f"submitted -> {parsed['status']}",
    )

    # Auto-record denial rows for the denial queue.
    if parsed["status"] == "DENIED":
        await _record_denial(claim_id, response, parsed)

    return {
        "claim_id": claim_id,
        "status": parsed["status"],
        "detail": parsed.get("detail", ""),
        "resolved_by": parsed.get("resolved_by", "RULE"),
        "response": response,
    }


@function_tool
async def check_claim_status(claim_id: str) -> dict:
    """Look up the current lifecycle state of a claim for the dashboard."""
    row = await database.query_one("SELECT * FROM claims WHERE claim_id = $1", claim_id)
    if not row:
        raise ValueError(f"no claim with id {claim_id}")
    return {
        "claim_id": row["claim_id"],
        "patient_fhir_id": row["patient_fhir_id"],
        "payer": row["payer"],
        "total_amount": float(row["total_amount"]) if row["total_amount"] else None,
        "status": row["status"],
        "resolved_by": row["resolved_by"],
        "submitted_at": str(row["submitted_at"]),
        "updated_at": str(row["updated_at"]),
    }


async def _record_denial(claim_id: str, response: dict, parsed: dict) -> None:
    reason_code = None
    from rcm_denials import parse_denial_reason
    reason_code, reason_text = parse_denial_reason(response)
    await database.execute(
        """
        INSERT INTO denials (claim_id, reason_code, reason_text, suggested_fix)
        VALUES ($1, $2, $3, $4)
        """,
        claim_id,
        reason_code,
        reason_text or parsed.get("detail", ""),
        None,
    )
    await audit.record(
        actor="log_denial",
        action="LOG_DENIAL",
        resource_type="Claim",
        resource_id=claim_id,
        summary=f"denial logged: {reason_code} {reason_text}",
    )


@function_tool
async def resubmit_claim(claim_id: str, fix_note: str = "") -> dict:
    """Re-submit a previously denied claim after a human-approved correction.
    Re-simulates the clearinghouse response and updates the claim state."""
    row = await database.query_one("SELECT * FROM claims WHERE claim_id = $1", claim_id)
    if not row:
        raise ValueError(f"no claim with id {claim_id}")

    await database.execute(
        "UPDATE claims SET status='SUBMITTED', updated_at=NOW() WHERE claim_id=$1",
        claim_id,
    )
    # Re-simulate with a different salt so a fixed claim can come back paid.
    import hashlib
    salt = f"{claim_id}-resubmit"
    h = int(hashlib.sha256(salt.encode()).hexdigest()[:8], 16)
    response = simulate_claim_response(claim_id)
    response["outcome"] = "complete"
    response["disposition"] = "Paid in full" if h % 2 == 0 else "Denied - modifier still missing"

    parsed = await parse_claim_response(response)
    await database.execute(
        """
        UPDATE claims SET status=$2, claim_response=$3::jsonb, resolved_by=$4, updated_at=NOW()
        WHERE claim_id=$1
        """,
        claim_id, parsed["status"], json.dumps(response), parsed.get("resolved_by", "RULE"),
    )
    # Close any OPEN denial for this claim if the resubmit succeeded.
    if parsed["status"] == "PAID":
        await _close_denial(claim_id)
    await audit.record(
        actor="resubmit_claim",
        action="RESUBMIT_CLAIM",
        resource_type="Claim",
        resource_id=claim_id,
        summary=f"resubmitted{(' ('+fix_note+')') if fix_note else ''} -> {parsed['status']}",
    )
    return {
        "claim_id": claim_id,
        "status": parsed["status"],
        "detail": parsed.get("detail", ""),
        "resolved_by": parsed.get("resolved_by", "RULE"),
    }


async def _close_denial(claim_id: str) -> None:
    await database.execute(
        "UPDATE denials SET fix_status='RESOLVED', resolved_at=NOW() WHERE claim_id=$1 AND fix_status='OPEN'",
        claim_id,
    )


async def list_claims(limit: int = 50) -> list[dict]:
    rows = await database.query(
        """
        SELECT c.claim_id, c.patient_fhir_id, c.payer, c.total_amount,
               c.codes, c.status, c.resolved_by, c.submitted_at, c.updated_at,
               d.reason_code, d.fix_status
        FROM claims c
        LEFT JOIN denials d ON d.claim_id = c.claim_id AND d.fix_status = 'OPEN'
        ORDER BY c.updated_at DESC
        LIMIT $1
        """,
        limit,
    )
    out = []
    for r in rows:
        out.append({
            "claim_id": r["claim_id"],
            "patient_fhir_id": r["patient_fhir_id"],
            "payer": r["payer"],
            "total_amount": float(r["total_amount"]) if r["total_amount"] else None,
            "codes": r["codes"] or [],
            "status": r["status"],
            "resolved_by": r["resolved_by"],
            "submitted_at": str(r["submitted_at"]),
            "updated_at": str(r["updated_at"]),
            "open_denial_reason": r["reason_code"],
        })
    return out
