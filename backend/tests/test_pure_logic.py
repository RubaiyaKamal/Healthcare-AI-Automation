"""Unit tests for pure logic that does not need live FHIR/Postgres/OpenAI."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

import registration
import eligibility
import duplicate_check


# ------------------------------------------------------------
# registration._validate + _build_fhir_patient
# ------------------------------------------------------------
class TestRegistrationValidation:
    def test_requires_core_fields(self):
        errors = registration._validate({"first_name": "A", "last_name": ""})
        assert any("missing required field: last_name" in e for e in errors)

    def test_rejects_future_dob(self):
        errors = registration._validate(
            {"first_name": "A", "last_name": "B", "dob": "2999-01-01"}
        )
        assert any("future" in e for e in errors)

    def test_rejects_bad_date(self):
        errors = registration._validate(
            {"first_name": "A", "last_name": "B", "dob": "04/12/1985"}
        )
        assert any("YYYY-MM-DD" in e for e in errors)

    def test_valid_form_passes(self):
        errors = registration._validate(
            {
                "first_name": "Maria",
                "last_name": "Lopez",
                "dob": "1985-04-12",
                "phone": "555-0102",
                "email": "m@example.com",
            }
        )
        assert errors == []

    def test_rejects_over_130(self):
        errors = registration._validate(
            {"first_name": "A", "last_name": "B", "dob": "1850-01-01", "phone": "555-0102"}
        )
        assert any("130" in e for e in errors)

    def test_build_fhir_patient_structure(self):
        data = {
            "first_name": "Maria",
            "last_name": "Lopez",
            "dob": "1985-04-12",
            "gender": "female",
            "phone": "555-0102",
            "email": "m@example.com",
            "insurer": "Acme Health",
            "member_id": "M12345",
        }
        p = registration._build_fhir_patient(data)
        assert p["resourceType"] == "Patient"
        assert p["name"][0]["family"] == "Lopez"
        assert p["birthDate"] == "1985-04-12"
        assert p["identifier"][0]["system"] == "urn:healthcare:auth:mrn"
        member_ids = [
            i for i in p["identifier"] if i["system"] == "urn:healthcare:auth:member"
        ]
        assert member_ids and member_ids[0]["value"] == "M12345"
        assert p["managingOrganization"]["display"] == "Acme Health"


# ------------------------------------------------------------
# eligibility._rule_based
# ------------------------------------------------------------
class TestEligibilityRules:
    CAT = {"type": {"coding": [{"display": "PPO"}]}}

    def test_inactive_cancelled_not_covered(self):
        r = eligibility._rule_based({"status": "cancelled"})
        assert r["status"] == "Not Covered"

    def test_expired_period_not_covered(self):
        r = eligibility._rule_based(
            {"status": "active", "period": {"start": "2025-01-01", "end": "2025-01-02"}}
        )
        assert r["status"] == "Not Covered"

    def test_future_start_not_covered(self):
        r = eligibility._rule_based(
            {"status": "active", "period": {"start": "2999-01-01"}}
        )
        assert r["status"] == "Not Covered"

    def test_active_open_covered(self):
        r = eligibility._rule_based({"status": "active", **self.CAT})
        assert r["status"] == "Covered"

    def test_prior_auth_detected(self):
        r = eligibility._rule_based(
            {"status": "active", **self.CAT, "subrogation": True, "class": [{"value": "requires prior authorization"}]}
        )
        assert r["status"] == "Needs Prior Auth"

    def test_prior_auth_via_contract_field(self):
        r = eligibility._rule_based(
            {"status": "active", **self.CAT, "contract": "prior authorization required"}
        )
        assert r["status"] == "Needs Prior Auth"


# ------------------------------------------------------------
# duplicate_check._dob_similarity
# ------------------------------------------------------------
class TestDobSimilarity:
    def test_exact(self):
        assert duplicate_check._dob_similarity("1985-04-12", "1985-04-12") == 1.0

    def test_same_year(self):
        assert duplicate_check._dob_similarity("1985-04-12", "1985-09-01") == 0.5

    def test_missing(self):
        assert duplicate_check._dob_similarity(None, "1985-04-12") == 0.0

    def test_different_year(self):
        assert duplicate_check._dob_similarity("1990-01-01", "1985-04-12") == 0.0