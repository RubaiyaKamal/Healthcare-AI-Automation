"""
Patient registration — creates a FHIR Patient + caches it in Postgres.

Pipeline enforced by the intake agent (and this module):
  1. validate required fields
  2. duplicate check (must run before this tool is called)
  3. create FHIR Patient resource
  4. upsert into local cache
  5. audit the create
"""

import json
import logging
import uuid
from datetime import date
from typing import Any

from agents import function_tool
from pydantic import BaseModel

import audit
import database

log = logging.getLogger(__name__)

REQUIRED_FIELDS = ("first_name", "last_name", "dob")
MAX_AGE_YEARS = 130


class PatientInput(BaseModel):
    """Patient form data used by validate_patient_data and register_patient.

    All fields optional except first/last/dob so the intake agent can submit
    whatever a clerk filled in and have the agent ask for the rest."""
    first_name: str
    last_name: str
    dob: str
    gender: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    insurer: str | None = None
    member_id: str | None = None
    middle_name: str | None = None
    mrn: str | None = None


def _validate(data: dict) -> list[str]:
    errors = []
    for f in REQUIRED_FIELDS:
        if not str(data.get(f, "")).strip():
            errors.append(f"missing required field: {f}")

    dob = str(data.get("dob") or "")
    if dob:
        from datetime import date

        try:
            d = date.fromisoformat(dob)
            if d > date.today():
                errors.append("dob cannot be in the future")
        except ValueError:
            errors.append("dob must be YYYY-MM-DD")

        if data.get("first_name") and data.get("last_name") and data.get("phone"):
            from datetime import date as _d

            try:
                dob_parsed = _d.fromisoformat(dob)
                years = (date.today() - dob_parsed).days / 365.25
                if years > MAX_AGE_YEARS:
                    errors.append(f"dob implies age > {MAX_AGE_YEARS}")
            except ValueError:
                pass

    if data.get("email") and "@" not in str(data["email"]):
        errors.append("invalid email address")
    if data.get("phone") and len(str(data["phone"]).replace("+", "")) < 7:
        errors.append("invalid phone number")
    return errors


def _build_fhir_patient(data: dict) -> dict:
    """Build a FHIR R4 Patient resource from validated form data."""
    if not data.get("mrn"):
        data["mrn"] = f"MRN-{uuid.uuid4().hex[:10].upper()}"

    identifier = [{"system": "urn:healthcare:auth:mrn", "value": data["mrn"]}]
    if data.get("member_id"):
        identifier.append({
            "system": "urn:healthcare:auth:member",
            "value": str(data["member_id"]),
        })

    name_parts: dict[str, Any] = {"family": data["last_name"]}
    if data.get("first_name"):
        name_parts["given"] = [data["first_name"]]
    if data.get("middle_name"):
        name_parts["given"] = name_parts.get("given", []) + [data["middle_name"]]
    name_parts["use"] = "official"

    telecom = []
    if data.get("phone"):
        telecom.append({"system": "phone", "value": data["phone"], "use": "mobile"})
    if data.get("email"):
        telecom.append({"system": "email", "value": data["email"]})

    address = None
    if data.get("address") or data.get("city"):
        addr: dict[str, Any] = {"use": "home"}
        if data.get("address"):
            addr["line"] = [data["address"]]
        if data.get("city"):
            addr["city"] = data["city"]
        if data.get("state"):
            addr["state"] = data["state"]
        if data.get("zip"):
            addr["postalCode"] = data["zip"]
        address = [addr]

    insurer_id = None
    if data.get("insurer"):
        insurer_id = {
            "system": "urn:healthcare:auth:payer",
            "value": data["insurer"],
        }

    return {
        "resourceType": "Patient",
        "name": [name_parts],
        "telecom": telecom,
        "gender": data.get("gender") or "unknown",
        "birthDate": data["dob"],
        "address": address or [],
        "identifier": identifier + ([insurer_id] if insurer_id else []),
        "managingOrganization": {
            "display": data.get("insurer") or "Self-Pay",
        },
        "meta": {"tag": [{"system": "urn:healthcare:auth", "code": "registered"}]},
    }


@function_tool
async def register_patient(data: PatientInput) -> dict:
    """Register a new patient. `data` must include: first_name, last_name, dob,
    and optionally gender, phone, email, address, city, state, zip, insurer,
    member_id, mrn.

    IMPORTANT: The intake agent MUST run validate_patient_data and
    check_for_duplicates BEFORE calling this tool.

    Returns {fhir_id, mrn, created: true}.
    """
    data = data.model_dump()
    errors = _validate(data)
    if errors:
        raise ValueError("Validation failed: " + "; ".join(errors))

    from fhir_client import get_client

    fhir_patient = _build_fhir_patient(data)
    created = get_client().create(fhir_patient)

    fhir_id = created.get("id")
    if not fhir_id:
        raise RuntimeError("FHIR server returned a Patient without an id")

    name = (fhir_patient.get("name") or [{}])[0]
    given = name.get("given") or []
    row = {
        "fhir_id": fhir_id,
        "first_name": given[0] if given else "",
        "last_name": name.get("family") or "",
        "dob": fhir_patient["birthDate"],
        "gender": fhir_patient.get("gender") or "",
        "mrn": data.get("mrn"),
        "phone": data.get("phone"),
        "email": data.get("email"),
        "address": {
            "line": [data["address"]] if data.get("address") else [],
            "city": data.get("city"),
            "state": data.get("state"),
            "postalCode": data.get("zip"),
        },
        "insurer": data.get("insurer"),
        "member_id": data.get("member_id"),
        "raw_fhir": created,
    }
    await database.execute(
        """
        INSERT INTO patients (fhir_id, first_name, last_name, dob, gender, mrn,
                              phone, email, address, insurer, member_id, raw_fhir)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11, $12::jsonb)
        ON CONFLICT (fhir_id) DO NOTHING
        """,
        row["fhir_id"],
        row["first_name"],
        row["last_name"],
        row["dob"],
        row["gender"],
        row["mrn"],
        row["phone"],
        row["email"],
        json.dumps(row["address"]),
        row["insurer"],
        row["member_id"],
        json.dumps(row["raw_fhir"]),
    )

    await audit.record_patient_create(
        "register_patient",
        fhir_id,
        f"registered {row['first_name']} {row['last_name']} mrn={row['mrn']}",
    )

    return {"fhir_id": fhir_id, "mrn": row["mrn"], "created": True}


@function_tool
async def validate_patient_data(data: PatientInput) -> dict:
    """Validate patient form data client-side before any write happens.
    Returns {valid: bool, errors: [str]}."""
    errors = _validate(data.model_dump())
    return {"valid": not errors, "errors": errors}