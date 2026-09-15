"""
Duplicate patient detection.

Strategy (safe by design — the AI never auto-merges):
  1. Exact SQL match on (first, last, dob)             -> definite duplicate
  2. Fuzzy SQL candidates via pg_trgm similarity       -> probabilistic candidates
  3. If steps 1-2 disagree or are ambiguous            -> LLM judges the edge case only
  4. No matter what, the LLM is never allowed to merge — it can only flag.

Every decision is written to duplicate_check_log.
"""

import logging
from typing import Any

from agents import function_tool
import database

log = logging.getLogger(__name__)


@function_tool
async def check_for_duplicates(
    first_name: str,
    last_name: str,
    dob: str,
    ai_judge: bool = True,
) -> dict:
    """Check whether a patient with these details already exists in the
    registry. Always call before registering a new patient.

    Returns:
      {
        "is_duplicate": bool,
        "match_type": "NONE" | "SQL_EXACT" | "SQL_FUZZY" | "LLM_ONLY",
        "matches": [ {...patient summary, similarity, match_reason} ],
        "ai_reasoning": str | None,
        "recommendation": "existing_patient" | "candidate_new" | "needs_review"
      }
    """

    # --- Step 1: exact match ---
    exact = await database.query(
        """
        SELECT fhir_id, first_name, last_name, dob, similarity(
            (first_name || ' ' || last_name), ($2 || ' ' || $3)
        ) AS sim
        FROM patients
        WHERE LOWER(first_name) = LOWER($2)
          AND LOWER(last_name) = LOWER($3)
          AND dob = $4
        LIMIT 5
        """,
        None,
        first_name,
        last_name,
        dob,
    )

    if exact:
        matches = [dict(r) for r in exact]
        await _log(match_type="SQL_EXACT", matches=matches, reason="exact name+dob match")
        return {
            "is_duplicate": True,
            "match_type": "SQL_EXACT",
            "matches": matches,
            "ai_reasoning": None,
            "recommendation": "existing_patient",
        }

    # --- Step 2: fuzzy candidates ---
    fuzzy = await database.query(
        """
        SELECT fhir_id, first_name, last_name, dob,
               similarity((first_name || ' ' || last_name), ($2 || ' ' || $3)) AS sim
        FROM patients
        WHERE dob IS NOT NULL
          AND (first_name || ' ' || last_name) % ($2 || ' ' || $3)
           OR (last_name || ' ' || first_name) % ($2 || ' ' || $3)
        ORDER BY sim DESC
        LIMIT 5
        """,
        None,
        first_name,
        last_name,
    )

    fuzzy_matches = [dict(r) for r in fuzzy]

    # --- Step 3: only involve the LLM when there are ambiguous candidates ---
    needs_ai = False
    ai_reasoning = None

    candidates = []
    for m in fuzzy_matches:
        name_sim = float(m.get("sim") or 0.0)
        dob_sim = _dob_similarity(m.get("dob"), dob)
        is_match = name_sim >= 0.55 and dob_sim >= 0.6
        candidates.append({
            "fhir_id": m["fhir_id"],
            "first_name": m["first_name"],
            "last_name": m["last_name"],
            "dob": str(m["dob"]),
            "similarity": round(name_sim, 4),
            "dob_similarity": round(dob_sim, 4),
            "match_reason": "high_similarity" if is_match else "borderline",
        })
        needs_ai = needs_ai or is_match

    if needs_ai and ai_judge:
        ai_reasoning = _llm_judge(first_name, last_name, dob, candidates)

    if ai_reasoning and ai_reasoning != "none":
        combined = _combine_heuristics_and_llm(candidates, ai_reasoning)
        await _log(match_type="LLM_ONLY", matches=candidates, reason=combined["ai_reasoning"])
        return combined

    if candidates:
        any_high = any(c["match_reason"] == "high_similarity" for c in candidates)
        await _log(
            match_type="SQL_FUZZY",
            matches=candidates,
            reason=f"fuzzy similarity candidates, ai_judge={ai_judge}",
        )
        return {
            "is_duplicate": any_high,
            "match_type": "SQL_FUZZY",
            "matches": candidates,
            "ai_reasoning": None,
            "recommendation": "existing_patient" if any_high else "candidate_new",
        }

    await _log(match_type="NONE", matches=[], reason="no exact or fuzzy matches")
    return {
        "is_duplicate": False,
        "match_type": "NONE",
        "matches": [],
        "ai_reasoning": None,
        "recommendation": "candidate_new",
    }


def _dob_similarity(a: Any, b: str) -> float:
    """0.0..1.0 — exact date = 1.0, same year = 0.5, else 0.0."""
    if not a:
        return 0.0
    a = str(a)
    if a == b:
        return 1.0
    if a[:4] == b[:4]:
        return 0.5
    return 0.0


def _llm_judge(first_name: str, last_name: str, dob: str, candidates: list[dict]) -> str:
    """Judge borderline cases. Returns 'none' to say 'not a duplicate', otherwise
    a string containing the matching fhir_id and a one-line reason."""
    from agents import Agent, Runner
    from config import INTAKE_MODEL, OPENAI_API_KEY

    if not OPENAI_API_KEY:
        return "none"

    cand_text = "\n".join(
        f"- {c['first_name']} {c['last_name']} ({c['dob']}) sim={c['similarity']} /dob_sim={c['dob_similarity']}"
        for c in candidates
    )

    agent = Agent(
        name="duplicate_judge",
        model=INTAKE_MODEL,
        instructions=(
            "You are a patient-matching reviewer. You decide whether a NEW incoming "
            "patient is the same person as an EXISTING record. You never merge records; "
            "you only flag. Use your best clinical-registration judgement on name "
            "variants (e.g. 'Bob' vs 'Robert', swapped names, typos) and date-of-birth "
            "proximity. Respond with exactly one JSON object: "
            '{"decision": "none" | "duplicate", "match_id": null | "<fhir_id>", "reason": "<one line>"}'
        ),
    )
    prompt = (
        f"New patient: {first_name} {last_name}, DOB {dob}.\n"
        f"Existing candidates:\n{cand_text}\n\n"
        "Return JSON only."
    )
    result = Runner.run_sync(agent, prompt)
    text = (result.final_output or "").strip()
    import json as _json
    try:
        parsed = _json.loads(text)
    except Exception:
        log.warning("LLM judge returned unparseable output: %r", text[:300])
        return "none"

    if parsed.get("decision") != "duplicate" or not parsed.get("match_id"):
        return "none"
    return f"{parsed['match_id']}: {parsed.get('reason', 'llm judged duplicate')}"


def _combine_heuristics_and_llm(candidates: list[dict], llm_reasoning: str) -> dict:
    """Merge a deterministic heuristic verdict with the LLM's judgement."""
    llm_match_id = llm_reasoning.split(":")[0].strip() if ":" in llm_reasoning else None

    high_match = next((c for c in candidates if c["match_reason"] == "high_similarity"), None)

    # LLM says duplicate and heuristics agree -> definite.
    if llm_match_id and high_match and high_match["fhir_id"] == llm_match_id:
        return {
            "is_duplicate": True,
            "match_type": "LLM_ONLY",
            "matches": candidates,
            "ai_reasoning": llm_reasoning,
            "recommendation": "existing_patient",
        }

    # LLM says duplicate on a candidate heuristics underweighted -> flag for review.
    if llm_match_id:
        return {
            "is_duplicate": True,
            "match_type": "LLM_ONLY",
            "matches": candidates,
            "ai_reasoning": llm_reasoning,
            "recommendation": "needs_review",
        }

    # LLM says not a duplicate but heuristics flagged high similarity.
    if high_match:
        return {
            "is_duplicate": True,
            "match_type": "LLM_ONLY",
            "matches": candidates,
            "ai_reasoning": llm_reasoning + " (dd: heuristic flagged high sim, llm said no)",
            "recommendation": "needs_review",
        }

    return {
        "is_duplicate": False,
        "match_type": "LLM_ONLY",
        "matches": candidates,
        "ai_reasoning": llm_reasoning,
        "recommendation": "candidate_new",
    }


async def _log(match_type: str, matches: list[dict], reason: str | None = None) -> None:
    for m in matches:
        await database.execute(
            """
            INSERT INTO duplicate_check_log
                (candidate_id, candidate_name, candidate_dob, existing_id, existing_name,
                 match_type, similarity, ai_decision, ai_reasoning)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            m.get("fhir_id"),
            f"{m.get('first_name')} {m.get('last_name')}",
            m.get("dob"),
            m.get("fhir_id"),
            f"{m.get('first_name')} {m.get('last_name')}",
            match_type,
            m.get("similarity"),
            "duplicate" if m.get("match_reason") else "none",
            reason,
        )
    if not matches:
        await database.execute(
            """
            INSERT INTO duplicate_check_log (candidate_id, match_type, ai_reasoning)
            VALUES ($1, $2, $3)
            """,
            None,
            match_type,
            reason,
        )