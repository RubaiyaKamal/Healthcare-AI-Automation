"""
Patient Portal Chatbot — the scoped, safety-first patient assistant.

This sits inside the real product surface (#20 Patient Communication +
#14 Triage). The design is deterministic and intentionally limited:

  - Intro is always scoped to a category: appointments / results & records /
    billing / symptoms. Quick replies keep conversations in safe lanes.
  - Appointments: next visit, reschedule (confirmed via the #1 scheduling
    queue), and visit prep.
  - Results & records: lab-result status and a READ-ONLY medication list.
    The bot NEVER interprets a value beyond normal/abnormal, never softens
    or explains an abnormal/critical result, and a human notification
    (#15) always fires in parallel.
  - Billing (#2/#13): plain-language balance and claim status only.
  - Triage (#14): exactly three closed-ended questions (red-flag symptoms,
    severity 0-10, duration). ANY red-flag answer => immediate hard-stop to
    emergency care — the conversation ends. Non-urgent => nurse-line callback
    is queued to a human. The bot never diagnoses or recommends treatment.

  Every exchange appends to chat_sessions and audit_log — the portal chat is
  not a private, unmonitored side-channel.

  No OpenAI key required: the safety boundaries are enforced by code, not by
  prompt-tuning.
"""

import logging
import uuid
from datetime import datetime, timezone

import audit
import database

log = logging.getLogger(__name__)

DISCLAIMER = (
    "\n\nThis isn't a substitute for medical advice. If this is an emergency, "
    "call 911 or go to your nearest ER."
)

OPENING_REPLY = (
    "Hi, I'm here to help with appointments, results, and messages. What can I help with today?"
)
OPENING_REPLIES = [
    "📅 Appointments",
    "🔬 Results & records",
    "🧾 Billing",
    "🤒 I'm not feeling well",
]

APPT_REPLIES = ["When is my next appointment?", "Can I reschedule?", "How do I prepare?"]
RESULTS_REPLIES = ["Are my lab results ready?", "Can I see my medication list?"]
BILLING_REPLIES = ["What do I owe?", "Can I see my claim status?"]

TRIAGE_RED_FLAG_REPLIES = [
    "Chest pain or pressure",
    "Trouble breathing",
    "Severe bleeding that won't stop",
    "Sudden weakness or trouble speaking",
    "Thoughts of harming myself",
    "None of these",
]
TRIAGE_SEVERITY_REPLIES = ["0–3 — mild", "4–6 — moderate", "7–10 — severe"]
TRIAGE_DURATION_REPLIES = ["Less than a day", "A few days", "A week or more"]

EMERGENCY_HARD_STOP = (
    "Because you've described a symptom that can be urgent, please stop here — don't wait for an "
    "answer from me.\n\n"
    "• Call 911 or go to your nearest emergency department immediately.\n"
    "• If you are with someone, tell them right now.\n"
    "• If thoughts of harming yourself are present, reach the 988 Suicide & Crisis Lifeline at 988 "
    "right now.\n\n"
    "Your care team has been notified as well. This conversation is not a substitute for "
    "emergency care."
)

# Pre-visit instructions keyed by keywords in the appointment's visit_type.
PREP_RULES = [
    ("physical", (
        "For your physical: bring a list of your current medications, any recent test results "
        "from other providers, and arrive 15 minutes early to update your information. Fasting is "
        "only required if your provider said so."
    )),
    ("follow-up", (
        "For your follow-up: bring your medication list and any notes or questions you want to "
        "cover with your provider. Your chart is already on file here."
    )),
    ("checkup", (
        "For your checkup: bring a photo ID, your insurance card, and a list of any symptoms or "
        "medications. Arrive 10–15 minutes early."
    )),
    ("lab", (
        "For your lab appointment: follow any fasting instructions on the order — usually nothing "
        "to eat or drink for 8–12 hours before a fasting draw. Bring your lab order and insurance card."
    )),
    ("imaging", (
        "For your imaging appointment: arrive 30 minutes early to check in. Wear comfortable "
        "clothing without metal clasps. Staff will review preparation with you before the scan."
    )),
    ("specialist", (
        "For your specialist visit: bring referral paperwork if you have it, your medication list, "
        "and any relevant results or notes from your referring provider."
    )),
]
PREP_DEFAULT = (
    "Bring a photo ID, your insurance card, and a current list of your medications. Arrive about "
    "15 minutes before your appointment time."
)

SEVERITY_HIGH = 7


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _short_intro(msg: str, limit: int = 240) -> str:
    return " ".join(msg.split())[:limit]


# ------------------------------------------------------------
# Pure logic (unit-testable, no DB)
# ------------------------------------------------------------

EMERGENCY_MATCHES = [
    "chest pain", "chest pressure", "tightness in my chest", "trouble breathing",
    "shortness of breath", "can't breathe", "cannot breathe", "hard to breathe",
    "difficulty breathing", "severe bleeding", "bleeding that won't stop",
    "unconscious", "fainted", "seizure", "stroke", "overdose", "suicide",
    "kill myself", "want to die", "self harm", "self-harm", "hurt myself",
    "harming myself", "harm myself", "call 911", "911", "emergency",
]

RED_FLAG_TOKENS = [
    "chest", "breath", "breathing", "bleeding", "weakness", "numb",
    "slurred", "harming myself", "harm myself", "hurting myself", "suicidal",
]


def detect_emergency(text: str) -> tuple[bool, str]:
    """Any urgent/self-harm language wins over everything else."""
    norm = _normalize(text)
    for kw in sorted(EMERGENCY_MATCHES, key=len, reverse=True):
        if kw in norm:
            return True, kw
    return False, ""


def red_flag_match(text: str) -> str | None:
    """Return the red-flag keyword present in this input, or None."""
    norm = _normalize(text)
    for kw in RED_FLAG_TOKENS:
        if kw in norm:
            return kw
    return None


def severity_from_text(text: str) -> int | None:
    """Parse '0'..'10', '10/10', 'moderate', 'severe', etc. None if unclear."""
    norm = _normalize(text)
    if "mild" in norm:
        return 1
    if "moderate" in norm:
        return 5
    if "severe" in norm or "worst" in norm:
        return 8
    if "fine" in norm:
        return 0
    # slide-safe numeric parse: '7', '10/10', '7 out of 10' -> 7 or 10
    for token in norm.replace("/", " ").split():
        if token.isdigit():
            v = int(token)
            if 0 <= v <= 10:
                return v
    return None


def _base_phase(phase: str) -> str:
    """Strip any state the phase carries, e.g. 'triage_duration:7' -> 'triage_duration'."""
    return phase.split(":", 1)[0]


def route_intent(message: str, phase: str) -> str:
    """Map a message + current chat phase to an intent code. Wrong-safe: when in
    doubt it returns a re-ask, never a new write.

    Codes: menu | appointments | results | billing | next_appointment |
           reschedule | reschedule_date | prep | appts_help | labs | meds |
           results_help | owed | claims | billing_help | triage_start |
           redflag | redflag_ask | severity | duration | fallback
    """
    norm = _normalize(message)
    base = _base_phase(phase)

    if any(k in norm for k in ("main menu", "back to menu", "start over", "go home")):
        return "menu"

    # Direct ask for the next appointment, no matter the phase.
    if any(k in norm for k in ("when is my next", "my next appointment", "next appointment")):
        return "next_appointment"

    # Triage entry takes priority when symptoms are described.
    if any(k in norm for k in (
        "not feeling well", "feel sick", "feeling sick", "feel unwell", "don't feel good",
        "don't feel well", "symptom", "symptoms", "sick today", "nauseous", "nausea",
        "dizzy", "fever", "headache", "throwing up", "vomit", "diarrhea",
        "something's wrong", "something is wrong", "urgent care", "need to see someone",
    )):
        return "triage_start"

    # Category selection (only from the menu).
    if base == "open":
        if any(k in norm for k in ("appointment", "appt", "schedule", "sched", "visit", "resched")):
            return "appointments"
        if any(k in norm for k in ("results", "records", "lab", "result", "medication", "medicine",
                                   "meds", "prescription")):
            return "results"
        if any(k in norm for k in ("bill", "owe", "owed", "balance", "statement", "claim",
                                   "charge", "insurance")):
            return "billing"
        return "fallback"

    # In-conversation routing.
    if base == "appts":
        if any(k in norm for k in ("next", "when", "upcoming")):
            return "next_appointment"
        if any(k in norm for k in ("resched", "reschedul", "move", "change", "postpone",
                                   "different", "another time")):
            return "reschedule"
        if any(k in norm for k in ("prep", "prepare", "bring", "instructions", "fast",
                                   "what do i need")):
            return "prep"
        return "appts_help"

    if base == "reschedule":
        return "reschedule_date"

    if base == "results":
        if any(k in norm for k in ("lab", "result", "ready", "test", "blood work", "panel")):
            return "labs"
        if any(k in norm for k in ("medic", "meds", "medicine", "prescription", "drug")):
            return "meds"
        return "results_help"

    if base == "billing":
        if any(k in norm for k in ("owe", "owed", "balance", "due", "amount")):
            return "owed"
        if any(k in norm for k in ("claim", "status", "insurance", "paid", "denied",
                                   "statement", "cover")):
            return "claims"
        return "billing_help"

    if base == "triage_first":
        if red_flag_match(message):
            return "redflag"
        if any(k in norm for k in ("none", "no", "not any", "neither", "nothing like")):
            return "severity"
        return "redflag_ask"

    if base == "triage_severity":
        return "severity"

    if base == "triage_duration":
        return "duration"

    return "fallback"


# ------------------------------------------------------------
# DB-backed answer builders
# ------------------------------------------------------------

async def _next_appointment(patient_fhir_id: str) -> dict | None:
    row = await database.query_one(
        """
        SELECT visit_type, provider, location, start_time, end_time
        FROM appointments
        WHERE patient_fhir_id = $1 AND status = 'SCHEDULED' AND start_time >= NOW()
        ORDER BY start_time
        LIMIT 1
        """,
        patient_fhir_id,
    )
    return dict(row) if row else None


async def _request_appointment(
    patient_fhir_id: str, kind: str, notes: str, requested_date: str | None = None
) -> dict:
    request_id = f"REQ-{uuid.uuid4().hex[:10].upper()}"
    await database.execute(
        """
        INSERT INTO appointment_requests
            (id, patient_fhir_id, kind, requested_date, notes)
        VALUES ($1, $2, $3, $4, $5)
        """,
        request_id, patient_fhir_id, kind, requested_date, notes,
    )
    return {"id": request_id, "kind": kind}


async def _lab_summary(patient_fhir_id: str) -> dict:
    """Return {reply, kind, data} for the latest labs. Never discloses values
    for ANOMALY/CRITICAL, and marks the human-notification flag."""
    rows = await database.query(
        """
        SELECT id, lab_name, status, notified
        FROM lab_results
        WHERE patient_fhir_id = $1
        ORDER BY COALESCE(resulted_at, created_at) DESC
        LIMIT 5
        """,
        patient_fhir_id,
    )
    if not rows:
        return {"reply": "I don't see any lab results on file for this account.",
                "kind": "results", "data": {}}

    pending = [r for r in rows if r["status"] == "PENDING"]
    normal = [r for r in rows if r["status"] == "NORMAL"]
    abnormal = [r for r in rows if r["status"] in ("ANOMALY", "CRITICAL")]

    if abnormal:
        worst = "critical" if any(r["status"] == "CRITICAL" for r in abnormal) else "notable"
        for r in rows:
            if r["notified"] is False:
                await database.execute(
                    "UPDATE lab_results SET notified = TRUE WHERE id = $1", r["id"]
                )
        await audit.record(
            actor="patient_portal_chatbot",
            action="PORTAL_ABNORMAL_RESULT",
            resource_type="LabResult",
            resource_id=patient_fhir_id,
            summary=(
                f"portal chatbot surfaced {worst} lab result; human notification "
                "dispatched via #15; no value disclosed in chat"
            ),
        )
        return {
            "reply": (
                "A recent result of yours has been flagged for your care team. Your provider has "
                "been notified and will contact you to discuss these results. To keep you safe, "
                "I can't share or explain that result in this chat."
            ) + DISCLAIMER,
            "kind": "results",
            "data": {"flagged_status": worst},
        }

    if normal:
        names = ", ".join(r["lab_name"] for r in normal)
        reply = f"Your lab ({names}) came back and is within the normal range."
        if pending:
            reply += f" {len(pending)} other test{'s' if len(pending) > 1 else ''} still pending."
        return {
            "reply": reply + DISCLAIMER,
            "kind": "results",
            "data": {"normal": [r["lab_name"] for r in normal],
                     "pending": [r["lab_name"] for r in pending]},
        }

    return {
        "reply": "Your labs aren't ready yet. You'll get a notification the moment they are — no "
                 "need to keep checking.",
        "kind": "results",
        "data": {"pending": [r["lab_name"] for r in pending]},
    }


async def _medications(patient_fhir_id: str) -> dict:
    rows = await database.query(
        """
        SELECT drug_name, strength, instructions
        FROM medications
        WHERE patient_fhir_id = $1 AND status = 'ACTIVE'
        ORDER BY drug_name
        """,
        patient_fhir_id,
    )
    if not rows:
        return {"reply": "No active medications are listed on this account.",
                "kind": "results", "data": {}}
    lines = [
        f"• {r['drug_name']}{': ' + r['strength'] if r['strength'] else ''} — {r['instructions'] or 'as directed'}"
        for r in rows
    ]
    reply = (
        "Here's your current medication list (read-only):\n" + "\n".join(lines)
        + "\n\nI can't change or recommend doses, and you shouldn't adjust any medication without "
        "talking to your provider. For refills or changes, message your care team."
    )
    return {"reply": reply + DISCLAIMER, "kind": "results",
            "data": {"medications": [dict(r) for r in rows]}}


async def _balance(patient_fhir_id: str) -> dict:
    row = await database.query_one(
        """
        SELECT COALESCE(SUM(balance_due), 0) AS total,
               COUNT(*) AS open_statements,
               COALESCE(SUM((status = 'DENIED')::int), 0) AS denied
        FROM claims
        WHERE patient_fhir_id = $1
          AND status IN ('SUBMITTED', 'PENDING', 'PARTIALLY_PAID', 'DENIED')
        """,
        patient_fhir_id,
    )
    total = row["total"] or 0
    count = row["open_statements"] or 0
    denied = row["denied"] or 0
    if count == 0:
        return {"reply": "You don't have any open billing statements on file.",
                "kind": "billing", "data": {"balance": 0.0, "open_statements": 0, "denied": 0}}
    reply = (
        f"You currently have ${float(total):,.2f} outstanding across {count} open statement"
        f"{'s' if count != 1 else ''}."
        + (f" {denied} of those {'is' if denied == 1 else 'are'} in a denied status and being "
           "reviewed by our billing team." if denied else "")
    )
    return {
        "reply": reply + "\n\nFor questions about a specific charge, call billing at (555) 010-2030.",
        "kind": "billing",
        "data": {"balance": float(total), "open_statements": count, "denied": denied},
    }


async def _claims_status(patient_fhir_id: str) -> dict:
    rows = await database.query(
        """
        SELECT payer, total_amount, status, submitted_at
        FROM claims
        WHERE patient_fhir_id = $1
        ORDER BY submitted_at DESC
        LIMIT 5
        """,
        patient_fhir_id,
    )
    if not rows:
        return {"reply": "You don't have any claims on file yet.",
                "kind": "billing", "data": {"claims": []}}
    labels = {
        "SUBMITTED": "submitted", "PENDING": "being processed", "PAID": "paid",
        "PARTIALLY_PAID": "partially paid", "DENIED": "denied",
        "ERROR": "needs attention", "DRAFT": "draft",
    }
    lines = [
        f"• ${float(r['total_amount'] or 0):,.2f} — {labels.get(r['status'], r['status'].lower())} "
        f"({r['payer'] or 'payer not listed'})"
        for r in rows
    ]
    return {
        "reply": ("Here's the status of your recent claims:\n" + "\n".join(lines))
        + "\n\nIf any claim needs a correction, our billing team handles it and will reach out to you.",
        "kind": "billing",
        "data": {"claims": [dict(r) for r in rows]},
    }


# ------------------------------------------------------------
# Conversation handler
# ------------------------------------------------------------

async def handle_message(
    *,
    session_id: str,
    patient_fhir_id: str,
    phase: str,
    message: str,
) -> dict:
    """One turn of a portal chat. Returns
    {reply, quick_replies, kind, phase, hard_stop, data?}."""
    text = message.strip()
    base = {
        "quick_replies": [],
        "kind": "info",
        "hard_stop": False,
        "data": {},
    }

    # Pre-scan: any urgent language hard-stops immediately, no matter where we are.
    is_emergency, kw = detect_emergency(text)
    if is_emergency:
        await audit.record(
            actor="patient_portal_chatbot",
            action="PORTAL_EMERGENCY_TRIGGERED",
            resource_type="ChatSession",
            resource_id=session_id,
            summary=f"emergency language detected ('{kw}'); hard stop issued to emergency care",
        )
        return {
            **base,
            "reply": EMERGENCY_HARD_STOP,
            "kind": "hard_stop",
            "phase": "hard_stop",
            "hard_stop": True,
        }

    # A hard stop is terminal — the conversation does NOT resume until the
    # patient starts a fresh session.
    if _base_phase(phase) == "hard_stop":
        return {
            **base,
            "reply": (
                "This conversation has ended — please follow the emergency guidance above. If you "
                "still need help, call 911 or go to your nearest ER."
            ),
            "kind": "hard_stop",
            "phase": "hard_stop",
            "hard_stop": True,
        }

    intent = route_intent(text, phase)
    log.debug("portal chat session=%s phase=%s intent=%s", session_id, phase, intent)

    if intent == "menu":
        return {**base, "reply": OPENING_REPLY, "quick_replies": OPENING_REPLIES,
                "kind": "intro", "phase": "open"}

    if intent == "appointments":
        return {**base, "reply": "Here's what I can help with for appointments:",
                "quick_replies": APPT_REPLIES, "kind": "appts", "phase": "appts"}

    if intent == "results":
        return {**base, "reply": "I can check your lab results or show your medication list:",
                "quick_replies": RESULTS_REPLIES, "kind": "results", "phase": "results"}

    if intent == "billing":
        return {**base, "reply": "I can give you a plain-language view of your account:",
                "quick_replies": BILLING_REPLIES, "kind": "billing", "phase": "billing"}

    if intent == "triage_start":
        reply = (
            "I'm sorry you're not feeling well. I can't diagnose, but I can connect you to the "
            "right care. First, a quick safety question — do you have any of these right now?"
        )
        lines = "\n".join(f"• {label}" for label in TRIAGE_RED_FLAG_REPLIES[:-1])
        return {**base, "reply": reply + "\n\n" + lines,
                "quick_replies": TRIAGE_RED_FLAG_REPLIES,
                "kind": "triage", "phase": "triage_first"}

    # ---------------- appointments ----------------
    if intent == "next_appointment":
        appt = await _next_appointment(patient_fhir_id)
        if not appt:
            await _request_appointment(
                patient_fhir_id, "BOOK",
                "auto-requested via portal chatbot (no upcoming visit on file)",
            )
            reply = (
                "You don't have any upcoming appointments scheduled. I've routed a message to our "
                "front desk to help you book one — they'll reach out to confirm."
            )
            return {**base, "reply": reply, "quick_replies": APPT_REPLIES,
                    "kind": "appts", "phase": "appts"}
        reply = (
            f"Your next visit is a {appt['visit_type']} with {appt['provider'] or 'your care team'} "
            f"on {appt['start_time'].strftime('%A, %b %-d, %Y')} at "
            f"{appt['start_time'].strftime('%-I:%M %p')}"
            + (f" at {appt['location']}" if appt.get("location") else "")
            + ".\n\nWant prep details or help rescheduling?"
        )
        return {**base, "reply": reply,
                "quick_replies": ["How do I prepare?", "Can I reschedule?", "Back to menu"],
                "kind": "appts", "phase": "appts",
                "data": {k: appt[k] for k in ("visit_type", "provider", "location", "start_time")}}

    if intent == "reschedule":
        return {
            **base,
            "reply": "Sure — what date and time would work better? You can say something like "
                     "'next Tuesday at 2 PM' or '2026-10-01 10:00'.",
            "kind": "appts",
            "phase": "reschedule",
        }

    if intent == "reschedule_date" or (phase == "reschedule" and intent == "fallback"):
        await _request_appointment(
            patient_fhir_id, "RESCHEDULE", notes=f"preferred: {_short_intro(text)}"
        )
        await audit.record(
            actor="patient_portal_chatbot",
            action="APPT_RESCHEDULE_REQUEST",
            resource_type="Patient",
            resource_id=patient_fhir_id,
            summary="portal chatbot queued reschedule request to #1 scheduling workflow",
        )
        return {
            **base,
            "reply": (
                f"I've sent a reschedule request for “{_short_intro(text)}” to our front desk. "
                "They'll confirm the new time with you through the scheduling workflow — nothing "
                "more needed from you."
            ),
            "quick_replies": APPT_REPLIES,
            "kind": "confirm",
            "phase": "appts",
        }

    if intent == "prep":
        appt = await _next_appointment(patient_fhir_id)
        vtype = (appt or {}).get("visit_type") or ""
        inst = PREP_DEFAULT
        vn = _normalize(vtype)
        for key, text_ in PREP_RULES:
            if key in vn:
                inst = text_
                break
        return {**base, "reply": inst + " I can also look up your next visit if you need.",
                "quick_replies": APPT_REPLIES, "kind": "appts", "phase": "appts"}

    if intent == "appts_help":
        return {**base, "reply": "I can help with your next appointment, rescheduling, or visit prep.",
                "quick_replies": APPT_REPLIES, "kind": "appts", "phase": "appts"}

    # ---------------- results ----------------
    if intent == "labs":
        result = await _lab_summary(patient_fhir_id)
        return {**base, **result, "phase": "results",
                "quick_replies": [*RESULTS_REPLIES, "Back to menu"]}

    if intent == "meds":
        result = await _medications(patient_fhir_id)
        return {**base, **result, "phase": "results",
                "quick_replies": [*RESULTS_REPLIES, "Back to menu"]}

    if intent == "results_help":
        return {**base, "reply": "I can check lab results or show your current medication list.",
                "quick_replies": RESULTS_REPLIES, "kind": "results", "phase": "results"}

    # ---------------- billing ----------------
    if intent == "owed":
        result = await _balance(patient_fhir_id)
        return {**base, **result, "phase": "billing",
                "quick_replies": [*BILLING_REPLIES, "Back to menu"]}

    if intent == "claims":
        result = await _claims_status(patient_fhir_id)
        return {**base, **result, "phase": "billing",
                "quick_replies": [*BILLING_REPLIES, "Back to menu"]}

    if intent == "billing_help":
        return {**base, "reply": "I can show what you owe or the status of your claims.",
                "quick_replies": BILLING_REPLIES, "kind": "billing", "phase": "billing"}

    # ---------------- triage ----------------
    if intent == "redflag" and _base_phase(phase) == "triage_first":
        await audit.record(
            actor="patient_portal_chatbot",
            action="PORTAL_EMERGENCY_TRIGGERED",
            resource_type="ChatSession",
            resource_id=session_id,
            summary=f"red-flag answer ('{red_flag_match(text)}'); hard stop issued to emergency care",
        )
        return {**base, "reply": EMERGENCY_HARD_STOP, "kind": "hard_stop",
                "phase": "hard_stop", "hard_stop": True}

    if intent == "redflag_ask" and _base_phase(phase) == "triage_first":
        return {
            **base,
            "reply": (
                "I want to be careful here — so I need a direct answer. Do you have any of the "
                "following right now? Please pick one."
            ),
            "quick_replies": TRIAGE_RED_FLAG_REPLIES,
            "kind": "triage",
            "phase": "triage_first",
        }

    if intent == "severity" and _base_phase(phase) == "triage_first":
        return {
            **base,
            "reply": "Thanks — that helps. How would you rate how bad you feel right now, on a "
                     "scale of 0–10 (0 = fine, 10 = the worst you've ever felt)?",
            "quick_replies": TRIAGE_SEVERITY_REPLIES,
            "kind": "triage",
            "phase": "triage_severity",
        }

    if intent == "severity" and _base_phase(phase) == "triage_severity":
        sev = severity_from_text(text)
        if sev is None:
            return {
                **base,
                "reply": "Just a number 0–10 works — 0 is fine, 10 is the worst you've ever felt.",
                "quick_replies": TRIAGE_SEVERITY_REPLIES,
                "kind": "triage",
                "phase": "triage_severity",
            }
        reply = (
            "Thanks. One last question — about how long has this been going on?"
            if sev < SEVERITY_HIGH else
            "Thank you — that level warrants a faster response, so a nurse will call you back "
            "soon. One last question: about how long has this been going on?"
        )
        return {**base, "reply": reply, "quick_replies": TRIAGE_DURATION_REPLIES,
                "kind": "triage", "phase": f"triage_duration:{sev}",
                "data": {"severity": sev, "fast_track": sev >= SEVERITY_HIGH}}

    if intent == "duration" and _base_phase(phase) == "triage_duration":
        sev_raw = phase.split(":", 1)[1] if ":" in phase else ""
        try:
            sev = int(sev_raw)
        except (TypeError, ValueError):
            sev = None
        notes = (
            f"symptom triage ({_short_intro(text, 120)}); severity {sev or 'not rated'}; "
            f"{'FAST-TRACK' if sev is not None and sev >= SEVERITY_HIGH else 'standard'} nurse callback"
        )
        await _request_appointment(patient_fhir_id, "NURSE_CALLBACK", notes=notes)
        await audit.record(
            actor="patient_portal_chatbot",
            action="PORTAL_NURSE_CALLBACK",
            resource_type="Patient",
            resource_id=patient_fhir_id,
            summary="non-urgent symptom triage completed; nurse-line callback queued to a human",
        )
        reply = (
            "Thanks — a nurse will call you back at the number on file within the next hour. If "
            "your symptoms get worse before then, call 911 or go to your nearest ER."
        )
        return {**base, "reply": reply + DISCLAIMER,
                "quick_replies": ["Back to menu", "I have another question"],
                "kind": "confirm", "phase": "triage_done",
                "data": {"severity": sev, "fast_track": sev is not None and sev >= SEVERITY_HIGH}}

    # ---------------- fallback ----------------
    reply = (
        "I'm here to help with appointments, results, billing, or getting you to the right care. "
        "Which of those would you like?"
    )
    return {**base, "reply": reply, "quick_replies": OPENING_REPLIES,
            "kind": "info", "phase": "open"}