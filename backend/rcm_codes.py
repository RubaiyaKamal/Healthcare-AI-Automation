"""
Medical coding reference + deterministic validation.

Design principle (carried from Phase 1): the LLM proposes, deterministic code
validates. This module owns the deterministic layer only — no LLM here.

  validate_codes(codes) -> {accepted: [...], rejected: [...]}

Every suggested code (from the LLM or a user) is checked against the local
`code_reference` table for:
  - existence (system + code must be present), and
  - billability (the `billable` flag must be true).

Unrecognized or non-billable codes are rejected automatically — never silently
kept on a claim.
"""

import logging

from agents import function_tool
import audit
import database

log = logging.getLogger(__name__)


def classify_reference_row(row: dict | None) -> dict:
    """Pure logic: given a code_reference row (or None), return a verdict.

    Used by validate_codes and unit tests alike. No I/O.
    """
    if row is None:
        return {
            "valid": False,
            "reason": "code not found in reference table",
        }
    if not row.get("billable", True):
        return {
            "valid": False,
            "reason": "code exists but is not billable",
        }
    return {
        "valid": True,
        "reason": "ok",
        "display": row.get("display"),
        "category": row.get("category"),
    }


def _normalize(codes: list) -> list[dict]:
    """Coerce list of {system, code, summary?} into clean dicts."""
    out = []
    for c in codes or []:
        if isinstance(c, str):
            out.append({"system": "CPT", "code": c.strip().upper()})
        elif isinstance(c, dict):
            out.append({
                "system": (c.get("system") or "CPT").strip(),
                "code": str(c.get("code") or "").strip().upper(),
                "summary": c.get("summary"),
            })
    return [c for c in out if c["code"]]


@function_tool
async def validate_codes(codes: list) -> dict:
    """Deterministically validate a list of medical codes against the reference
    table. Each item is {system: 'ICD-10-CM'|'CPT'|'HCPCS', code: '...'} (an
    optional 'summary' carries an LLM rationale for audit). Returns
    {accepted: [{system, code, display, category}], rejected: [{system, code,
    reason, summary}], total_valid, total_rejected}."""
    normalized = _normalize(codes)
    if not normalized:
        return {
            "accepted": [],
            "rejected": [],
            "total_valid": 0,
            "total_rejected": 0,
        }

    accepted, rejected = [], []
    for c in normalized:
        row = await database.query_one(
            "SELECT system, code, display, billable, category FROM code_reference WHERE system=$1 AND code=$2",
            c["system"],
            c["code"],
        )
        verdict = classify_reference_row(dict(row) if row else None)
        entry = {**c, **verdict}
        if verdict["valid"]:
            accepted.append({
                "system": c["system"],
                "code": c["code"],
                "display": verdict.get("display"),
                "category": verdict.get("category"),
                "summary": c.get("summary"),
            })
        else:
            rejected.append({
                "system": c["system"],
                "code": c["code"],
                "reason": verdict["reason"],
                "summary": c.get("summary"),
            })

    await audit.record(
        actor="validate_codes",
        action="VALIDATE_CODES",
        resource_type="CodeReference",
        summary=f"validated {len(normalized)} codes -> {len(accepted)} ok / {len(rejected)} rejected",
    )

    return {
        "accepted": accepted,
        "rejected": rejected,
        "total_valid": len(accepted),
        "total_rejected": len(rejected),
    }


async def classify_patient_note_row(row: dict) -> dict:
    """Post-processing of a coding_suggestions row for the dashboard."""
    return {
        "id": row["id"],
        "patient_fhir_id": row["patient_fhir_id"],
        "note_excerpt": (row["note_text"] or "")[:120],
        "accepted_codes": row["accepted_codes"] or [],
        "rejected_codes": row["rejected_codes"] or [],
        "resolved_by": row["resolved_by"],
        "created_at": str(row["created_at"]),
    }