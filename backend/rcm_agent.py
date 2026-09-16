"""
Revenue Cycle Agent — the umbrella agent for Phase 2.

Orchestrates the real-world sequence:
  eligibility -> coding -> prior auth (if required) -> build claim -> submit
  claim -> track status -> denial fix (if denied)

Hands off to the Coding and Prior Auth sub-agents, and directly uses the
eligibility / claim tools. Runs synchronously in a threadpool from the
FastAPI layer, exactly like intake_agent.py.
"""

import json
import logging

from agents import Agent, Runner
from config import INTAKE_MODEL, OPENAI_API_KEY
import eligibility
import rcm_coding
import rcm_prior_auth
import rcm_claims

log = logging.getLogger(__name__)


RCM_INSTRUCTIONS = f"""
You are the Revenue Cycle Agent for HealthFlow AI. You take a clinical note
for a patient and drive it through the full claim lifecycle. Follow this
EXACT sequence, never skipping a step:

1. ELIGIBILITY — call check_eligibility(patient_fhir_id). If the patient is
   'Not Covered', stop and report that the claim cannot proceed.

2. CODING — hand off to the CodingSubAgent with the clinical note. It will
   propose and validate codes. Insist that it returns ONLY validated codes
   (accepted by validate_codes). If the note is too sparse to code, ask the
   user for more detail and stop.

3. PRIOR AUTH — for each procedure code the payer requires prior auth for,
   call check_prior_auth_required(payer, procedure_code). If required, hand
   off to the PriorAuthSubAgent to draft the request, then explicitly wait for
   the human to approve submission. Never auto-submit: set prior_auth_status
   to REQUIRED and block claim submission until a request is SUBMITTED.

4. BUILD CLAIM — call build_claim with the VALIDATED codes and payer.

5. SUBMIT CLAIM — call submit_claim, then check_claim_status.

6. REPORT — summarize the final status (PAID / DENIED / PARTIALLY_PAID /
   PENDING), what codes were used, and the next action. If DENIED, suggest
   the denial fix flow.

CRITICAL SAFETY RULES:
- NEVER put an unvalidated code on a claim.
- NEVER decide prior-auth approval — that is the payer's decision.
- NEVER auto-submit a prior-auth request without explicit human approval.
- NEVER fabricate a payer or clinical note. Use only data you retrieved.
"""


def build_revenue_cycle_agent(*, model: str | None = None) -> Agent:
    coding_agent = rcm_coding.build_coding_agent(model=model)
    prior_auth_agent = rcm_prior_auth.build_prior_auth_agent(model=model)

    return Agent(
        name="RevenueCycleAgent",
        model=model or INTAKE_MODEL,
        instructions=RCM_INSTRUCTIONS,
        handoffs=[coding_agent, prior_auth_agent],
        tools=[
            eligibility.check_eligibility,
            rcm_claims.build_claim,
            rcm_claims.submit_claim,
            rcm_claims.check_claim_status,
            rcm_prior_auth.check_prior_auth_required,
        ],
    )


def _extract_tool_calls(result) -> list[dict]:
    """Pull ({tool, args}) from a RunResult's new_items list. Handles both the
    plain-dict and pydantic raw forms of a function_call item."""
    calls = []
    for item in (result.new_items or []):
        if getattr(item, "type", "") != "tool_call_item":
            continue
        raw = getattr(item, "raw_item", item)
        name = raw.get("name") if isinstance(raw, dict) else getattr(raw, "name", None)
        if not name:
            continue
        args_raw = (
            raw.get("arguments")
            if isinstance(raw, dict)
            else getattr(raw, "arguments", None)
        )
        args = {}
        if args_raw:
            try:
                args = json.loads(args_raw)
            except Exception:
                args = {"raw": args_raw}
        calls.append({"tool": name, "args": args})
    return calls


def run_revenue_cycle_sync(task: dict) -> dict:
    """Run the revenue cycle agent over a single task dict:
    {patient_fhir_id, clinical_note, payer?}. Returns output + tool calls."""
    if not OPENAI_API_KEY:
        return {
            "output": (
                "OpenAI API key is not configured. Set OPENAI_API_KEY in .env "
                "to enable the revenue cycle agent."
            ),
            "tool_calls": [],
        }

    patient_fhir_id = (task.get("patient_fhir_id") or "").strip()
    clinical_note = (task.get("clinical_note") or "").strip()
    payer = (task.get("payer") or "").strip()

    if not patient_fhir_id or not clinical_note:
        return {
            "output": "Both patient_fhir_id and clinical_note are required.",
            "tool_calls": [],
        }

    agent = build_revenue_cycle_agent()
    prompt = (
        f"Patient FHIR ID: {patient_fhir_id}\n"
        f"Payer: {payer or 'unknown — look up from the patient record or ask'}\n"
        f"Clinical note:\n{clinical_note[:4000]}\n\n"
        "Process this note through the full revenue cycle."
    )
    result = Runner.run_sync(agent, prompt)

    return {
        "output": result.final_output or "",
        "tool_calls": _extract_tool_calls(result),
        "trace_id": str(getattr(result, "trace_id", "") or ""),
    }