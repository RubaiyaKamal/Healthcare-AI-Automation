"""
Denial handling loop.

When parse_claim_response returns DENIED, a denial row is stored with the
reason. suggest_denial_fix asks the LLM to propose a correction (e.g. wrong
modifier, missing prior auth, incorrect code) that a human reviews before
resubmit_claim runs.

Same safety boundary as everywhere else in the system: the LLM suggests, the
human approves, the deterministic layer executes.
"""

import json
import logging

from agents import Agent, Runner, function_tool
from config import INTAKE_MODEL, OPENAI_API_KEY
import audit
import database

log = logging.getLogger(__name__)


def parse_denial_reason(response: dict) -> tuple[str | None, str]:
    """Deterministic extraction of a denial reason from a ClaimResponse-like
    dict. Returns (reason_code, reason_text)."""
    disposition = (response.get("disposition") or "")
    reasons = response.get("processNote") or response.get("addItem") or []
    if isinstance(reasons, list):
        for note in reasons:
            text = None
            if isinstance(note, dict):
                text = note.get("text") or (note.get("noteNumber") and str(note.get("noteNumber")))
            if text:
                return (str(note.get("code") or "") or None, str(text))
    return (None, disposition or "Denied by payer")


@function_tool
async def log_denial(
    claim_id: str,
    reason_code: str | None,
    reason_text: str,
) -> dict:
    """Record a denied claim in the denial queue. This is called automatically
    when submit_claim.parse_claim_response returns DENIED."""
    await database.execute(
        """
        INSERT INTO denials (claim_id, reason_code, reason_text)
        VALUES ($1, $2, $3)
        """,
        claim_id, reason_code, reason_text,
    )
    await audit.record(
        actor="log_denial",
        action="LOG_DENIAL",
        resource_type="Claim",
        resource_id=claim_id,
        summary=f"denial logged: {reason_code or '?'} {reason_text[:80]}",
    )
    return {"claim_id": claim_id, "reason_code": reason_code, "reason_text": reason_text}


@function_tool
async def suggest_denial_fix(denial_id: int) -> dict:
    """Ask the LLM to suggest a correction for an OPEN denial. Returns the
    suggestion text — this must be human-reviewed before resubmit_claim."""
    row = await database.query_one(
        """
        SELECT d.id, d.claim_id, d.reason_code, d.reason_text, d.suggested_fix,
               c.payer, c.codes, c.prior_auth_status
        FROM denials d
        LEFT JOIN claims c ON c.claim_id = d.claim_id
        WHERE d.id = $1
        """,
        denial_id,
    )
    if not row:
        raise ValueError(f"no denial with id {denial_id}")

    if row["suggested_fix"]:
        return {"denial_id": denial_id, "suggested_fix": row["suggested_fix"], "cache_hit": True}

    claim_context = {
        "reason_code": row["reason_code"],
        "reason_text": row["reason_text"],
        "payer": row["payer"],
        "codes": row["codes"],
        "prior_auth_status": row["prior_auth_status"],
    }

    suggestion = None
    if OPENAI_API_KEY:
        agent = Agent(
            name="denial_fix_suggester",
            model=INTAKE_MODEL,
            instructions=(
                "You help a billing specialist fix a denied insurance claim. "
                "Given the denial reason and claim context, propose the single "
                "most likely correction. Options to consider: wrong/missing "
                "modifier, code needs prior authorization, code not covered, "
                "invalid code, missing documentation, resubmission as-is after "
                "timing out. Output exactly one JSON object: "
                '{"fix": "<what to change>", "explanation": "<one line>"}. '
                "Never resubmit or approve anything yourself."
            ),
        )
        result = Runner.run_sync(agent, f"Denial context: {json.dumps(claim_context)[:2000]}")
        try:
            parsed = json.loads(result.final_output or "{}")
            suggestion = parsed.get("fix") or (parsed.get("explanation") or "")
        except Exception:
            log.warning("denial fix suggester returned non-JSON: %r", (result.final_output or "")[:200])
            suggestion = (result.final_output or "").strip() or None

    if not suggestion:
        suggestion = f"Review claim for: {row['reason_text'][:120]}"

    await database.execute(
        "UPDATE denials SET suggested_fix=$2 WHERE id=$1",
        denial_id, suggestion,
    )
    await audit.record(
        actor="suggest_denial_fix",
        action="SUGGEST_DENIAL_FIX",
        resource_type="Denial",
        resource_id=str(denial_id),
        summary="LLM suggested fix for open denial",
    )
    return {"denial_id": denial_id, "suggested_fix": suggestion, "cache_hit": False}


async def list_denials(limit: int = 30) -> list[dict]:
    rows = await database.query(
        """
        SELECT d.id, d.claim_id, d.reason_code, d.reason_text, d.suggested_fix,
               d.fix_status, d.created_at, p.first_name, p.last_name
        FROM denials d
        LEFT JOIN claims c ON c.claim_id = d.claim_id
        LEFT JOIN patients p ON p.fhir_id = c.patient_fhir_id
        ORDER BY d.created_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [
        {
            "id": r["id"],
            "claim_id": r["claim_id"],
            "reason_code": r["reason_code"],
            "reason_text": r["reason_text"],
            "suggested_fix": r["suggested_fix"],
            "fix_status": r["fix_status"],
            "created_at": str(r["created_at"]),
            "patient_name": (
                f"{r['first_name']} {r['last_name']}".strip()
                if r["first_name"] and r["last_name"] else None
            ),
        }
        for r in rows
    ]