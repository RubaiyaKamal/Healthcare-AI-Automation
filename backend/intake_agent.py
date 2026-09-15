"""
Intake Agent — takes front-desk registration data and walks the patient through
registration. Hard-enforced workflow:

  1. validate_patient_data       (no writes allowed on invalid data)
  2. check_for_duplicates        (MUST run before register_patient)
  3. register_patient            (creates FHIR Patient + cache)
  4. human-in-the-loop confirm   (creates session for local usage)

The agent may ask follow-up questions for missing fields, but it will NOT
call register_patient until duplicate check passes or a human overrides.
"""

from agents import Agent, Runner

from config import INTAKE_MODEL, OPENAI_API_KEY
import registration
import duplicate_check
import patient_lookup


DUPLICATE_GUARD = f"""
You are the Patient Intake Agent at a clinic front desk.

CRITICAL WORKFLOW — follow it in this exact order for every new registration:

1. If any of first_name, last_name, dob is missing from what the front-desk
   clerk gives you, ask politely for the missing fields. It is fine to ask
   one follow-up question at a time.

2. Call validate_patient_data with the full form. If it returns errors,
   repeat them back to the clerk and do NOT proceed until fixed.

3. Call check_for_duplicates with first_name, last_name, dob.
   - If it returns is_duplicate=true, tell the clerk an existing record was
     found, show the matching patient(s), and DO NOT call register_patient.
     Ask the clerk to confirm whether this is truly a new patient.
   - If is_duplicate=false, proceed to step 4.

4. ONLY AFTER duplicates are cleared: call register_patient. Report back the
   new FHIR id, MRN, and confirm full name + DOB to the clerk for a step-verific.

5. Always end by stating what was completed and the patient's FHIR id.

NEVER call register_patient before check_for_duplicates.
NEVER invent or fabricate patient data. Only use values the clerk provided
or that you retrieved from an actual tool call.
NEVER log or repeat full PHI (SSN, full DOB) in chat if you can avoid it —
use shorthand like "DOB 1978" or "b. 1978" when confirming.
"""


def build_intake_agent(*, model: str | None = None, tools: list | None = None) -> Agent:
    agent = Agent(
        name="PatientIntakeAgent",
        model=model or INTAKE_MODEL,
        instructions=DUPLICATE_GUARD,
        tools=tools or [
            registration.validate_patient_data,
            duplicate_check.check_for_duplicates,
            registration.register_patient,
            patient_lookup.get_patient,
        ],
    )
    return agent


def run_intake_sync(messages: list[dict]) -> dict:
    """Run the intake agent against a message history. Returns the final output
    plus any tool calls, so the frontend can render a transcript."""
    if not OPENAI_API_KEY:
        return {
            "output": "OpenAI API key is not configured. Set OPENAI_API_KEY in .env to enable the intake agent.",
            "tool_calls": [],
        }

    agent = build_intake_agent()
    result = Runner.run_sync(agent, input=messages)

    calls = []
    for item in (result.new_items or []):
        details = (item.get("step_details") or {})
        for step in details.get("tool_calls") or []:
            calls.append({
                "tool": step.get("name", ""),
                "args": (step.get("arguments") or step.get("input") or {}),
            })

    return {
        "output": result.final_output or "",
        "tool_calls": calls,
        "trace_id": str(getattr(result, "trace_id", "") or ""),
    }