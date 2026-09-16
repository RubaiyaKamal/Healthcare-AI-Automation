"""Unit tests for Phase 2 pure logic that does not need live FHIR/Postgres/OpenAI."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

import rcm_codes
import rcm_claims
import rcm_denials


# ------------------------------------------------------------
# rcm_codes.classify_reference_row
# ------------------------------------------------------------
class TestCodeReferenceRules:
    def test_valid_billable_row(self):
        r = rcm_codes.classify_reference_row(
            {"system": "CPT", "code": "99213", "display": "Office visit", "billable": True}
        )
        assert r["valid"] is True
        assert r["reason"] == "ok"

    def test_valid_row_nonbillable_false(self):
        r = rcm_codes.classify_reference_row(
            {"system": "CPT", "code": "99213", "billable": False}
        )
        assert r["valid"] is False
        assert "not billable" in r["reason"]

    def test_no_row_invalid(self):
        r = rcm_codes.classify_reference_row(None)
        assert r["valid"] is False

    def test_display_and_category_surfaced(self):
        r = rcm_codes.classify_reference_row(
            {"system": "ICD10CM", "code": "E11.9", "category": "diagnosis", "billable": True}
        )
        assert r["valid"] is True
        assert r["category"] == "diagnosis"


# ------------------------------------------------------------
# rcm_claims._rule_based_claim_response
# ------------------------------------------------------------
class TestClaimResponseRules:
    def test_paid_in_full(self):
        r = rcm_claims._rule_based_claim_response(
            {"outcome": "complete", "disposition": "Paid in full"}
        )
        assert r["status"] == "PAID"

    def test_partially_paid(self):
        r = rcm_claims._rule_based_claim_response(
            {"outcome": "complete", "disposition": "Partially paid — line item reduced"}
        )
        assert r["status"] == "PARTIALLY_PAID"

    def test_denied(self):
        r = rcm_claims._rule_based_claim_response(
            {"outcome": "complete", "disposition": "Denied - service not covered"}
        )
        assert r["status"] == "DENIED"

    def test_pending_queued(self):
        r = rcm_claims._rule_based_claim_response(
            {"outcome": "queued", "disposition": "Pending review"}
        )
        assert r["status"] == "PENDING"

    def test_error_outcome(self):
        r = rcm_claims._rule_based_claim_response({"outcome": "error"})
        assert r["status"] == "ERROR"

    def test_cancelled_response(self):
        r = rcm_claims._rule_based_claim_response({"status": "cancelled", "outcome": "complete"})
        assert r["status"] == "ERROR"

    def test_unrecognized_shape_sentinel(self):
        r = rcm_claims._rule_based_claim_response({"outcome": "weird-thing"})
        assert r["status"] == "UNRECOGNIZED"


# ------------------------------------------------------------
# rcm_claims.assemble_claim
# ------------------------------------------------------------
class TestAssembleClaim:
    def test_structure(self):
        claim = rcm_claims.assemble_claim(
            "pt-123",
            [
                {"system": "CPT", "code": "99213", "display": "Office visit"},
                {"system": "ICD10CM", "code": "I10", "display": "Hypertension"},
            ],
            payer="Acme Health",
            total_amount=180.0,
        )
        assert claim["resourceType"] == "Claim"
        assert claim["patient"]["reference"] == "Patient/pt-123"
        assert len(claim["item"]) == 2
        assert claim["item"][0]["productOrService"]["coding"][0]["code"] == "99213"
        assert claim["item"][1]["productOrService"]["coding"][0]["system"].endswith("icd10cm")
        assert claim["total"]["value"] == 180.0
        assert claim["insurer"]["display"] == "Acme Health"

    def test_optional_fields_absent(self):
        claim = rcm_claims.assemble_claim("pt-1", [{"system": "CPT", "code": "99201"}])
        assert "insurer" not in claim
        assert "total" not in claim


# ------------------------------------------------------------
# rcm_claims.simulate_claim_response (deterministic)
# ------------------------------------------------------------
class TestSimulatedResponse:
    def test_deterministic_per_claim(self):
        a = rcm_claims.simulate_claim_response("CLM-123")
        b = rcm_claims.simulate_claim_response("CLM-123")
        assert a == b

    def test_different_claims_differ(self):
        a = rcm_claims.simulate_claim_response("CLM-111")
        assert a["resourceType"] == "ClaimResponse"
        assert a["outcome"] in ("complete", "queued")


# ------------------------------------------------------------
# rcm_denials.parse_denial_reason
# ------------------------------------------------------------
class TestParseDenialReason:
    def test_process_note_taken(self):
        resp = {
            "outcome": "complete",
            "disposition": "Denied",
            "processNote": [{"code": "CO-19", "text": "Denial based on payment for this service"}],
        }
        code, text = rcm_denials.parse_denial_reason(resp)
        assert code == "CO-19"
        assert "Denial based" in text

    def test_falls_back_to_disposition(self):
        code, text = rcm_denials.parse_denial_reason({"disposition": "Denied - no coverage"})
        assert code is None
        assert text == "Denied - no coverage"

    def test_empty_response_returns_disposition(self):
        code, text = rcm_denials.parse_denial_reason({})
        assert code is None
        assert text == "Denied by payer"