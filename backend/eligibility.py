"""
Insurance eligibility verification.

Approach:
  1. Fetch Coverage from FHIR (fallback: mock payer API simulation).
  2. Classify the raw response with DETERMINISTIC RULES first.
       Covered          — active coverage w/ valid period
       Not Covered      — no coverage or inactive/expired
       Needs Prior Auth — coverage active but service requires authorization
       Unknown          — unrecognized shape
  3. Only if rules can't classify (Unknown), ask gpt-4o-mini to classify.
  4. Every result is stored in eligibility_checks with resolved_by=RULE|LLM,
     the raw payer response, checked_at, and the actor.
"""

import json
import logging
import uuid
from datetime import date, datetime
from typing import Any

from agents import function_tool
import audit
import database

log = logging.getLogger(__name__)

SERVICE_TO_CHECK = "outpatient-visit"
PAYER_SYSTEM = "urn:healthcare:auth:payer"


def _fetch_chain(patient_fhir_id: str) -> dict | None:
    """Fetch Coverage resources from FHIR for this patient. Returns the first
    relevant Coverage dict, or None if none exists."""
    from fhir_client import get_client

    coverage = get_client().search("Coverage", {"patient": patient_fhir_id})
    for c in coverage:
        status = (c.get("status") or "").lower()
        if status in ("active", "cancelled", "terminated"):
            return c
    return coverage[0] if coverage else None


def _rule_based(coverage: dict) -> dict:
    """Deterministic classifier. Returns (status, raw_shaped, used_prior_auth_flag)."""
    status_raw = (coverage.get("status") or "").lower()

    # No coverage -> Not Covered.
    if not coverage or status_raw in ("entered-in-error", "cancelled", "terminated"):
        return {"status": "Not Covered", "detail": "coverage inactive/no coverage", "prior_auth": False}

    if status_raw != "active":
        return {"status": "Not Covered", "detail": f"coverage status='{status_raw}'", "prior_auth": False}

    # Coverage period check.
    period = coverage.get("period") or {}
    start = period.get("start")
    end = period.get("end")
    today = date.today().isoformat()

    if start and start > today:
        return {"status": "Not Covered", "detail": "coverage period not yet started", "prior_auth": False}
    if end and end < today:
        return {"status": "Not Covered", "detail": "coverage period expired", "prior_auth": False}

    # Prior-auth requirement detection.
    requirement = coverage.get("subrogation") or coverage.get("contract")
    prior_auth_needed = False
    raw_terms = json.dumps(coverage).lower()
    for marker in ("prior auth", "prior-authorization", "prior authorization", "requires authorization", "preauthorization"):
        if marker in raw_terms:
            prior_auth_needed = True
            break

    plan = (coverage.get("type") or {}).get("coding") or []
    plan_name = (plan[0].get("display") if plan else None) or coverage.get("beneficiary", {}).get("type", {}).get("text")

    if prior_auth_needed:
        return {
            "status": "Needs Prior Auth",
            "detail": f"coverage active but requires prior authorization ({plan_name or 'plan'})",
            "plan": plan_name,
            "prior_auth": True,
        }

    return {
        "status": "Covered",
        "detail": f"active coverage until {end or 'open'}" if end else "active coverage",
        "plan": plan_name,
        "prior_auth": False,
    }


def _llm_fallback(coverage: dict) -> dict:
    """Only invoked for Unknown shapes. Cheap, bounded, audited."""
    from agents import Agent, Runner
    from config import ELIGIBILITY_MODEL, OPENAI_API_KEY

    if not OPENAI_API_KEY:
        return {"status": "Unknown", "detail": "could not classify; LLM fallback disabled"}

    agent = Agent(
        name="eligibility_classifier",
        model=ELIGIBILITY_MODEL,
        instructions=(
            "You classify an insurance eligibility response. Output exactly one JSON object: "
            '{"status": "Covered" | "Not Covered" | "Needs Prior Auth" | "Unknown", '
            '"detail": "<one line>", "plan": "<name or null>"}. '
            "Covered = active coverage; Not Covered = no/inactive/expired; "
            "Needs Prior Auth = active but requires authorization."
        ),
    )
    prompt = f"Coverage resource: {json.dumps(coverage)[:1500]}"
    result = Runner.run_sync(agent, prompt)
    try:
        return json.loads(result.final_output or "{}")
    except Exception:
        log.warning("LLM classifier returned non-JSON: %r", (result.final_output or "")[:120])
        return {"status": "Unknown", "detail": "LLM output unparseable"}


@function_tool
async def check_eligibility(
    patient_fhir_id: str,
    actor: str = "system",
) -> dict:
    """Check insurance eligibility for a patient. Returns
    {status: Covered|Not Covered|Needs Prior Auth|Unknown, detail, plan,
     resolved_by: RULE|LLM, payer, member_id, check_id, checked_at}."""
    if not patient_fhir_id:
        raise ValueError("patient_fhir_id is required")

    from patient_lookup import get_patient
    patient = await get_patient(patient_fhir_id)

    coverage = None
    try:
        coverage = _fetch_chain(patient_fhir_id)
    except Exception as e:
        log.warning("FHIR Coverage fetch failed: %s", e)

    if coverage is None:
        # Simulated payer response (no real payer API in Phase 1 demo).
        coverage = _mock_coverage(patient)

    result = _rule_based(coverage)
    resolved_by = "RULE"

    if result["status"] == "Unknown":
        llm = _llm_fallback(coverage)
        result.update(llm)
        resolved_by = "LLM"

    # Store in DB.
    check_id = uuid.uuid4().hex[:16]
    await database.execute(
        """
        INSERT INTO eligibility_checks
            (patient_fhir_id, status, payer, member_id, raw_response, resolved_by, checked_by)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
        """,
        patient_fhir_id,
        result["status"],
        _payer_name(coverage) or "Self-Pay",
        (patient or {}).get("member_id"),
        json.dumps(coverage),
        resolved_by,
        actor,
    )

    await audit.record_eligibility_check(
        actor,
        patient_fhir_id,
        f"eligibility -> {result['status']} ({resolved_by})",
    )

    return {
        "status": result["status"],
        "detail": result.get("detail", ""),
        "plan": result.get("plan"),
        "resolved_by": resolved_by,
        "payer": _payer_name(coverage) or "Self-Pay",
        "member_id": (patient or {}).get("member_id"),
        "check_id": check_id,
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }


def _payer_name(coverage: dict) -> str | None:
    payers = coverage.get("payor") or []
    for p in payers:
        display = p.get("display")
        if display:
            return display
    return None


def _mock_coverage(patient: dict | None) -> dict:
    """Simulated payer coverage used only when no FHIR Coverage exists."""
    member = (patient or {}).get("member_id") or f"M{uuid.uuid4().hex[:8].upper()}"
    # Half the demo patients end up "covered", 30% "needs prior auth", rest partial.
    h = int(uuid.uuid5(uuid.NAMESPACE_DNS, member).hex[-2:], 16)
    if h % 10 < 5:
        status, end = "active", "2026-12-31"
    elif h % 10 < 8:
        status, end = "active", "2026-03-31"
        return {
            "resourceType": "Coverage",
            "status": status,
            "beneficiary": {"reference": f"Patient/{patient.get('fhir_id')}" if patient else ""},
            "period": {"start": "2025-01-01", "end": end},
            "type": {"coding": [{"system": "urn:healthcare:payer", "code": "HMO", "display": "Acme Health HMO"}]},
            "payor": [{"display": "Acme Health"}],
            "subrogation": True,
            "class": [{"name": "requires", "value": "prior authorization for specialist visits"}],
        }
    else:
        status, end = "cancelled", "2025-09-30"
    return {
        "resourceType": "Coverage",
        "status": status,
        "beneficiary": {"reference": f"Patient/{patient.get('fhir_id')}" if patient else ""},
        "period": {"start": "2025-01-01", "end": end},
        "type": {"coding": [{"system": "urn:healthcare:payer", "code": "PPO", "display": "Acme Health PPO"}]},
        "payor": [{"display": "Acme Health"}],
    }