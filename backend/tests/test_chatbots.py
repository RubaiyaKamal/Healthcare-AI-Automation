"""Unit tests for Phase 3 chatbot pure logic — no live FHIR/Postgres/OpenAI."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

import site_chatbot
import patient_chatbot


# ------------------------------------------------------------
# Site visitor chatbot
# ------------------------------------------------------------
class TestSiteEmergency:
    def test_clinical_refused_returns_intro_path(self):
        r = site_chatbot.respond("I want a prescription for my pain")
        assert r["kind"] == "clinical_refusal"
        assert "can't provide medical advice" in r["reply"]

    def test_never_answers_emergency_clinical(self):
        r = site_chatbot.respond("my chest hurts and it is hard to breathe")
        assert r["kind"] == "clinical_refusal"

    def test_emergency_signal_blocks_other_intents(self):
        assert site_chatbot.detect_emergency("I am having chest pain, call 911")[0] is True
        assert site_chatbot.detect_emergency("what does HealthFlow AI do?")[0] is False
        assert site_chatbot.detect_emergency("thoughts of self-harm")[0] is True


class TestSiteIntents:
    def test_what_does_it_do(self):
        r = site_chatbot.respond("What does HealthFlow AI do?")
        assert r["kind"] == "intro"
        assert "Front Desk & Patient Access" in r["reply"]
        assert "Revenue Cycle" in r["reply"]

    def test_pricing_routes_to_demo(self):
        r = site_chatbot.respond("How does pricing work?")
        assert r["kind"] == "pricing"
        assert "demo" in r["reply"].lower()

    def test_hipaa_honest(self):
        r = site_chatbot.respond("Is this HIPAA compliant?")
        assert r["kind"] == "hipaa"
        assert "not HIPAA-certified" in r["reply"]

    def test_epic_cerner_integration(self):
        r = site_chatbot.respond("Does this integrate with Epic or Cerner?")
        assert r["kind"] == "integration"
        assert "FHIR" in r["reply"]

    def test_demo_intent_asks_for_details(self):
        r = site_chatbot.respond("Can I book a demo?")
        assert r["kind"] == "demo_collect"
        assert r["wants_demo"] is True

    def test_fallback_offers_connect(self):
        r = site_chatbot.respond("is there parking near your office")
        assert r["kind"] == "fallback"
        assert "connect you with our team" in r["reply"]


class TestDemoRequestValidation:
    def test_valid(self):
        assert site_chatbot.validate_demo_request("Sam Ortiz", "sam@acme.org", "Riverside Gen") == []

    def test_rejects_missing_fields(self):
        errors = site_chatbot.validate_demo_request("", "not-an-email", "")
        assert any("name" in e for e in errors)
        assert any("email" in e for e in errors)
        assert any("hospital" in e for e in errors)

    def test_rejects_bad_email(self):
        errors = site_chatbot.validate_demo_request("Sam", "sam@nowhere", "Riv Gen")
        assert any("email" in e for e in errors)


# ------------------------------------------------------------
# Patient portal chatbot
# ------------------------------------------------------------
class TestPortalEmergency:
    def test_chest_pain_hard_stop(self):
        is_em, kw = patient_chatbot.detect_emergency("I have chest pain right now")
        assert is_em and "chest pain" in kw

    def test_shortness_of_breath_hard_stop(self):
        assert patient_chatbot.detect_emergency("can't breathe well")[0] is True

    def test_self_harm_language_hard_stop(self):
        assert patient_chatbot.detect_emergency("I want to harm myself")[0] is True

    def test_normal_text_not_emergency(self):
        assert patient_chatbot.detect_emergency("when is my next appointment")[0] is False


class TestPortalRouting:
    def test_open_phase_appointments_category(self):
        assert patient_chatbot.route_intent("Can you help with appointments?", "open") == "appointments"

    def test_open_phase_billing_category(self):
        assert patient_chatbot.route_intent("billing question", "open") == "billing"

    def test_direct_next_appointment_any_phase(self):
        assert patient_chatbot.route_intent("When is my next appointment?", "appts") == "next_appointment"

    def test_triage_entry_from_any_phase(self):
        assert patient_chatbot.route_intent("I'm not feeling well", "open") == "triage_start"
        assert patient_chatbot.route_intent("I have a headache", "appts") == "triage_start"

    def test_reschedule_inside_appts(self):
        assert patient_chatbot.route_intent("Can I reschedule?", "appts") == "reschedule"

    def test_prep_inside_appts(self):
        assert patient_chatbot.route_intent("How do I prepare?", "appts") == "prep"

    def test_labs_inside_results(self):
        assert patient_chatbot.route_intent("Are my lab results ready?", "results") == "labs"

    def test_meds_inside_results(self):
        assert patient_chatbot.route_intent("Can I see my medication list?", "results") == "meds"

    def test_owed_inside_billing(self):
        assert patient_chatbot.route_intent("What do I owe?", "billing") == "owed"

    def test_claims_inside_billing(self):
        assert patient_chatbot.route_intent("Can I see my claim status?", "billing") == "claims"

    def test_reschedule_date_phase(self):
        assert patient_chatbot.route_intent("next Tuesday at 2pm", "reschedule") == "reschedule_date"


class TestPortalRedFlags:
    def test_red_flag_detected(self):
        assert patient_chatbot.red_flag_match("Sudden weakness or trouble speaking") == "weakness"
        assert patient_chatbot.red_flag_match("Chest pain or pressure") == "chest"
        assert patient_chatbot.red_flag_match("Thoughts of harming myself") == "harming myself"

    def test_none_of_these_is_not_red_flag(self):
        assert patient_chatbot.red_flag_match("None of these") is None

    def test_symptom_without_red_flag_is_ask(self):
        # "a headache" contains no red-flag tokens; the chatbot must NOT hard-stop
        # or diagnose. It re-asks the closed-ended red-flag question.
        intent = patient_chatbot.route_intent("I have a headache", "triage_first")
        assert intent in ("triage_start", "redflag_ask")

    def test_none_answer_moves_to_severity(self):
        assert patient_chatbot.route_intent("None of these", "triage_first") == "severity"


class TestSeverityParsing:
    def test_numeric(self):
        assert patient_chatbot.severity_from_text("7") == 7
        assert patient_chatbot.severity_from_text("10/10") == 10
        assert patient_chatbot.severity_from_text("0") == 0

    def test_words(self):
        assert patient_chatbot.severity_from_text("mild") == 1
        assert patient_chatbot.severity_from_text("moderate") == 5
        assert patient_chatbot.severity_from_text("severe") == 8

    def test_ambiguous(self):
        assert patient_chatbot.severity_from_text("I feel weird") is None


class TestPreparationRules:
    def test_physical_lookup(self):
        for key, text in patient_chatbot.PREP_RULES:
            if key == "physical":
                assert "medications" in text
                return
        pytest.fail("physical prep rule missing")

    def test_default_is_safe(self):
        assert "15 minutes" in patient_chatbot.PREP_DEFAULT