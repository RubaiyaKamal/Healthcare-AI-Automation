"""
AI-powered medical coding.

LLM proposes ICD-10/CPT/HCPCS codes from a clinical note; the deterministic
layer (rcm_codes.validate_codes) validates every one of them against the code
reference table. The sub-agent only ever returns *validated* codes.

Every proposal + validation outcome is persisted to coding_suggestions — the
audit evidence that an AI suggestion was reviewed by a deterministic layer
before it could reach a claim.
"""

import json
import logging
import uuid

from agents import Agent, Runner, function_tool
from config import INTAKE_MODEL, OPENAI_API_KEY
import audit
import database
import rcm_codes

log = logging.getLogger(__name__)

CODING_INSTRUCTIONS = """
You are a medical coder's assistant. You are presented with a clinical note
(or encounter/diagnosis text).

Your ONLY job is to propose ICD-10-CM diagnosis codes and CPT/HCPCS procedure
codes that are supported by the note. Rules:

1. Never invent facts. Base every code on something explicitly in the note.
   If the note is too sparse to support a code confidently, say so and ask for
   more detail instead of guessing.
2. Prefer specificity but avoid overcoding — do not add a diagnosis the note
   does not document.
3. Output ONLY a JSON array. Each element:
   {"system": "ICD-10-CM"|"CPT"|"HCPCS", "code": "XXXXX",
    "summary": "one-line clinical rationale", "confidence": 0.0-1.0}
4. If codes cannot be suggested, output an empty array [].
"""


async def _persist_suggestion(
    patient_fhir_id: str | None,
    encounter_fhir_id: str | None,
    note_text: str,
    suggested: list,
    validated: dict,
) -> None:
    await database.execute(
        """
        INSERT INTO coding_suggestions
            (patient_fhir_id, encounter_fhir_id, note_text,
             suggested_codes, validated_codes, accepted_codes, rejected_codes)
        VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7::jsonb)
        """,
        patient_fhir_id,
        encounter_fhir_id,
        note_text,
        json.dumps(suggested),
        json.dumps(validated.get("accepted", [])),
        json.dumps(validated.get("accepted", [])),
        json.dumps(validated.get("rejected", [])),
    )
    await audit.record(
        actor="coding_sub_agent",
        action="CODING_SUGGESTION",
        resource_type="Patient",
        resource_id=patient_fhir_id,
        summary=(
            f"suggested {len(suggested)} codes -> "
            f"{validated.get('total_valid', 0)} accepted / "
            f"{validated.get('total_rejected', 0)} rejected"
        ),
    )


@function_tool
async def suggest_medical_codes(
    clinical_note: str,
    patient_fhir_id: str | None = None,
) -> dict:
    """Propose ICD-10-CM / CPT / HCPCS codes from a clinical note using an LLM.
    Returns {suggested: [{system, code, summary, confidence}]}. These are RAW
    proposals — you MUST call validate_codes on the result before using them on
    a claim."""
    if not clinical_note or not clinical_note.strip():
        raise ValueError("clinical_note is required")

    if not OPENAI_API_KEY:
        return {
            "suggested": [],
            "note": "OpenAI API key not configured; LLM coding disabled.",
        }

    agent = Agent(
        name="coding_proposer",
        model=INTAKE_MODEL,
        instructions=CODING_INSTRUCTIONS,
    )
    prompt = f"Clinical note:\n{clinical_note.strip()[:4000]}"
    result = Runner.run_sync(agent, prompt)

    suggested = []
    try:
        parsed = json.loads(result.final_output or "[]")
        for item in parsed if isinstance(parsed, list) else []:
            if not isinstance(item, dict):
                continue
            suggested.append({
                "system": (item.get("system") or "CPT").strip(),
                "code": str(item.get("code") or "").strip().upper(),
                "summary": item.get("summary", ""),
                "confidence": item.get("confidence"),
            })
    except Exception:
        log.warning("coding proposer returned non-JSON: %r", (result.final_output or "")[:200])
        suggested = []

    return {
        "suggested": [c for c in suggested if c["code"]],
        "note": "LLM proposals — pending deterministic validation",
    }


async def process_coding(
    clinical_note: str,
    patient_fhir_id: str | None = None,
    encounter_fhir_id: str | None = None,
    actor: str = "system",
) -> dict:
    """Full coding pipeline: LLM propose -> deterministic validate -> audit-log.

    This is the entry point used by the coding sub-agent and the /coding API.
    Returns the validated result plus the raw proposals."""
    proposal = await suggest_medical_codes(clinical_note, patient_fhir_id)
    validated = await rcm_codes.validate_codes(proposal.get("suggested", []))

    record = {
        "patient_fhir_id": patient_fhir_id,
        "encounter_fhir_id": encounter_fhir_id,
        "note_excerpt": clinical_note.strip()[:200],
        "suggested": proposal.get("suggested", []),
        "accepted": validated.get("accepted", []),
        "rejected": validated.get("rejected", []),
        "resolved_by": "LLM_PROPOSE_DETERMINISTIC_VALIDATE",
    }
    await _persist_suggestion(
        patient_fhir_id,
        encounter_fhir_id,
        clinical_note,
        proposal.get("suggested", []),
        validated,
    )
    await audit.record(
        actor=actor,
        action="CODING_PIPELINE",
        resource_type="Patient",
        resource_id=patient_fhir_id,
        summary=f"coding pipeline -> {len(validated.get('accepted', []))} accepted / {len(validated.get('rejected', []))} rejected",
    )
    return record


def build_coding_agent(*, model: str | None = None) -> Agent:
    """Sub-agent that proposes + validates codes and only returns clean ones."""
    return Agent(
        name="CodingSubAgent",
        model=model or INTAKE_MODEL,
        instructions=(
            "You are the medical coding sub-agent. Given a clinical note: "
            "1) call suggest_medical_codes, 2) call validate_codes on the "
            "proposals, 3) return ONLY the codes in the accepted list, "
            "explaining why each was chosen. If the note is too sparse to code "
            "confidently, ask for the missing information instead of guessing. "
            "Never put an unvalidated code on a claim."
        ),
        tools=[suggest_medical_codes, rcm_codes.validate_codes],
    )


async def list_coding_suggestions(limit: int = 20) -> list[dict]:
    rows = await database.query(
        "SELECT * FROM coding_suggestions ORDER BY created_at DESC LIMIT $1",
        limit,
    )
    return [await rcm_codes.classify_patient_note_row(dict(r)) for r in rows]