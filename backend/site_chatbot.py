"""
Site Visitor Chatbot — pre-sales assistant for the marketing site.

Deterministic intent router scoped to hospital/clinic decision-makers:

  - What HealthFlow AI does       -> category-based answer (Front Desk,
                                     Revenue Cycle, Clinical Workflow, etc.)
  - How does pricing work?        -> routes to Contact / demo booking,
                                     never quotes numbers
  - Is this HIPAA compliant?      -> honest, points to /security, never
                                     claims certification that isn't true
  - Can I book a demo?            -> captures name/email/hospital, stores
                                     a sales lead (demo_requests)
  - Epic/Cerner integration       -> answers from the EHR adapter capability
  - Fallback                      -> "I'd love to connect you with our team…"

HARD RULES:
  - NEVER answer clinical questions.
  - NEVER pretend to know a specific hospital's live data.
  - NEVER make compliance claims that haven't been verified.

No OpenAI key needed — replies are fully deterministic so marketing copy
stays consistent and auditable.
"""

import logging
import uuid

import audit
import database

log = logging.getLogger(__name__)

INTRO_REPLY = (
    "Hi, I'm the HealthFlow AI assistant. I help with questions about the "
    "platform and can point you to live demos. What would you like to know?"
)
INTRO_REPLIES = [
    "What does HealthFlow AI do?",
    "How does pricing work?",
    "Is this HIPAA compliant?",
    "Can I book a demo?",
    "Does this integrate with Epic or Cerner?",
]

CATEGORY_BOARD = [
    (
        "Front Desk & Patient Access",
        "intake & registration (#3), scheduling (#1), insurance eligibility (#12), prior authorization (#6)",
    ),
    (
        "Revenue Cycle",
        "medical coding (#5), billing & claims (#2), denials management, full revenue cycle automation (#13)",
    ),
    (
        "Clinical Workflow",
        "clinical documentation (#4), patient triage & symptom assessment (#14), lab result processing (#15)",
    ),
    (
        "Patient Engagement",
        "patient follow-up (#7), patient communication & support (#20), the patient portal assistant",
    ),
    (
        "Operations",
        "fraud detection (#9), no-show prediction (#10), staff scheduling (#16), inventory (#17), referrals (#18), records extraction (#19)",
    ),
]

WHAT_REPLY = (
    "HealthFlow AI automates the end-to-end workflows a hospital or clinic runs every day:\n\n"
    + "\n".join(f"• {name} — {mods}" for name, mods in CATEGORY_BOARD)
    + "\n\n7 of those automations are live as working demos today (intake, eligibility, and the "
    "revenue cycle — coding, claims, prior auth, denials). Patient data is captured once and every "
    "module reads and appends to that same FHIR record — no re-entry anywhere. See the Solutions "
    "page for status on the full roadmap."
)
WHAT_REPLIES = ["Can I book a demo?", "Is this HIPAA compliant?", "Which modules are live?"]

PRICING_REPLY = (
    "We don't publish pricing here because it depends on your facility size and the modules you "
    "need. I can connect you with our team for a tailored demo and a quote for your environment. "
    "Want me to set that up?"
)
PRICING_REPLIES = ["Yes — book a demo", "No thanks, just browsing"]

HIPAA_REPLY = (
    "Straight answer: HealthFlow AI is not HIPAA-certified today. The current build is a local "
    "sandbox with synthetic data only, built to be audit-ready — every action is logged, and RBAC "
    "is planned — but it is not ready for production PHI. See the Security & Compliance page for "
    "exactly what we do now and what's on the roadmap to production posture."
)
HIPAA_REPLIES = ["What does HealthFlow AI do?", "Can I book a demo?"]

INTEGRATIONS_REPLY = (
    "Today the platform is FHIR-native — it reads and writes standard FHIR resources, so any EHR "
    "with a FHIR API can connect. Epic, Cerner, and athenahealth adapters are on our roadmap behind "
    "a single EHR-adapter interface (listed on the Security page). If you tell me which EHR you're "
    "on, I'll route that to our team to confirm current interoperability for your environment."
)
INTEGRATIONS_REPLIES = ["Can I book a demo?", "Is this HIPAA compliant?"]

DEMO_INTRO_REPLY = (
    "Absolutely — I'd love to set that up. Let me get a few details to route you to the right person."
)
DEMO_CONFIRM_TEMPLATE = (
    "Thanks {name}! Your demo request for {hospital} has been routed to our sales team. You'll hear "
    "from us at {email} within one business day to schedule a call. Anything else I can help with?"
)
DEMO_CONFIRM_REPLIES = ["What does HealthFlow AI do?", "Is this HIPAA compliant?"]

CLINICAL_REFUSAL_REPLY = (
    "I'm the HealthFlow AI platform assistant — I can't provide medical advice, and I don't have "
    "access to any hospital's live patient data. For anything clinical, please contact your "
    "provider's office directly. Is there something about the platform I can help with instead?"
)
CLINICAL_REFUSAL_REPLIES = ["What does HealthFlow AI do?", "Can I book a demo?"]

FALLBACK_REPLY = (
    "Thanks for your question — I'm a narrow assistant and that's outside what I can answer "
    "confidently. I'd love to connect you with our team for that — want me to set up a quick call? "
    "Or I can point you to the live demos in the meantime."
)
FALLBACK_REPLIES = ["Can I book a demo?", "Which modules are live?"]

CLINICAL_KEYWORDS = [
    "pain", "symptom", "prescri", "dosage", "dose", "medication", "diagnos",
    "my shoulder", "my knee", "my back", "fever", "rash", "headache", "vomit",
    "my results", "my labs", "appointment for me", "book me", "sick", "hurt",
    "treat", "cure", "insulin", "blood pressure", "glucose",
]
EMERGENCY_KEYWORDS = [
    "chest pain", "trouble breathing", "shortness of breath", "can't breathe",
    "severe bleeding", "unconscious", "seizure", "stroke", "overdose",
    "suicide", "kill myself", "self-harm", "emergency", "call 911",
]
DEMO_KEYWORDS = ["book a demo", "book demo", "schedule a demo", "request a demo", "demo", "quick call", "set up a call"]
PRICING_KEYWORDS = ["pric", "cost", "quote", "how much", "subscription", "what do you charge"]
HIPAA_KEYWORDS = ["hipaa", "complian", "secure", "security", "sox", "phi", "privacy", "certified", "baa"]
EHR_KEYWORDS = [
    "epic", "cerner", "athenahealth", "athena", "ehr", "emr", "integrat",
    "interface", "api", "fhir", "adapter", "interoperab",
]
INTRO_KEYWORDS = ["what does healthflow", "what is healthflow", "what can healthflow", "what does the platform", "how does healthflow", "which modules", "what modules", "capabilities", "features", "what do you do", "about healthflow"]

DISCLAIMER_CLINICAL = (
    "\n\nI'm not able to give medical advice. If this is an emergency, call 911 or go to your nearest ER."
)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def detect_emergency(text: str) -> tuple[bool, str]:
    """Pre-scan every input for urgent/self-harm language. If matched, the
    caller must hard-stop — this takes priority over any routing."""
    norm = _normalize(text)
    for kw in sorted(EMERGENCY_KEYWORDS, key=len, reverse=True):
        if kw in norm:
            return True, kw
    return False, ""


def route_intent(message: str) -> str:
    """Classify a message into a site-chatbot intent code.

    Codes: intro | demo | pricing | hipaa | integration | clinical | fallback
    """
    norm = _normalize(message)
    if not norm:
        return "fallback"

    if any(k in norm for k in DEMO_KEYWORDS):
        return "demo"

    if any(k in norm for k in PRICING_KEYWORDS):
        return "pricing"

    if any(k in norm for k in HIPAA_KEYWORDS):
        return "hipaa"

    if any(k in norm for k in EHR_KEYWORDS):
        return "integration"

    if any(k in norm for k in CLINICAL_KEYWORDS):
        return "clinical"

    if any(k in norm for k in INTRO_KEYWORDS):
        return "intro"

    return "fallback"


def respond(message: str) -> dict:
    """Deterministic reply for a single site-visitor turn. Returns
    {reply, kind, quick_replies, wants_demo: bool}."""
    is_emergency, _kw = detect_emergency(message)
    if is_emergency:
        return {
            "reply": CLINICAL_REFUSAL_REPLY,
            "kind": "clinical_refusal",
            "quick_replies": CLINICAL_REFUSAL_REPLIES,
            "wants_demo": False,
        }

    intent = route_intent(message)

    if intent == "demo":
        return {
            "reply": DEMO_INTRO_REPLY,
            "kind": "demo_collect",
            "quick_replies": [],
            "wants_demo": True,
        }
    if intent == "pricing":
        return {"reply": PRICING_REPLY, "kind": "pricing", "quick_replies": PRICING_REPLIES, "wants_demo": False}
    if intent == "hipaa":
        return {"reply": HIPAA_REPLY, "kind": "hipaa", "quick_replies": HIPAA_REPLIES, "wants_demo": False}
    if intent == "integration":
        return {"reply": INTEGRATIONS_REPLY, "kind": "integration", "quick_replies": INTEGRATIONS_REPLIES, "wants_demo": False}
    if intent == "clinical":
        return {"reply": CLINICAL_REFUSAL_REPLY, "kind": "clinical_refusal", "quick_replies": CLINICAL_REFUSAL_REPLIES, "wants_demo": False}
    if intent == "intro":
        return {"reply": WHAT_REPLY, "kind": "intro", "quick_replies": WHAT_REPLIES, "wants_demo": False}

    return {"reply": FALLBACK_REPLY, "kind": "fallback", "quick_replies": FALLBACK_REPLIES, "wants_demo": False}


VALID_EMAIL_ROOTS = (".com", ".org", ".net", ".edu", ".io", ".gov", ".ai")


def validate_demo_request(name: str, email: str, hospital: str) -> list[str]:
    """Lightweight lead validation. Returns a list of field errors (empty = OK)."""
    errors = []
    if not name or not name.strip() or len(name.strip()) < 2:
        errors.append("name is required")
    if not email or "@" not in email or not any(email.lower().endswith(r) for r in VALID_EMAIL_ROOTS):
        errors.append("a valid email is required")
    if not hospital or not hospital.strip() or len(hospital.strip()) < 2:
        errors.append("hospital/clinic name is required")
    return errors


async def store_demo_request(name: str, email: str, hospital: str, message: str = "") -> dict:
    """Persist a sales lead. Returns {id, name, email, hospital, reply}."""
    name = name.strip()
    email = email.strip().lower()
    hospital = hospital.strip()
    message = (message or "").strip()

    errors = validate_demo_request(name, email, hospital)
    if errors:
        return {"ok": False, "errors": errors, "id": None}

    lead_id = f"DEMO-{uuid.uuid4().hex[:10].upper()}"
    await database.execute(
        """
        INSERT INTO demo_requests (id, name, email, hospital, message)
        VALUES ($1, $2, $3, $4, $5)
        """,
        lead_id, name, email, hospital, message or None,
    )
    await audit.record(
        actor="site_chatbot",
        action="DEMO_REQUEST",
        resource_type="DemoRequest",
        resource_id=lead_id,
        summary=f"demo request: {hospital} ({email})",
    )
    log.info("demo request captured: %s %s <%s>", lead_id, hospital, email)

    return {
        "ok": True,
        "id": lead_id,
        "name": name,
        "email": email,
        "hospital": hospital,
        "reply": DEMO_CONFIRM_TEMPLATE.format(name=name, hospital=hospital, email=email),
        "quick_replies": DEMO_CONFIRM_REPLIES,
    }