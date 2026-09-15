"""
Agent tools for patient lookup.

- get_patient(fhir_id)         — read from FHIR + sync Postgres cache
- search_patients_by_name_dob  — search FHIR by name/DOB, sync cache

Every lookup writes an audit row via audit.record_patient_read.
"""

import json
from typing import Any

from agents import function_tool
import audit
import database


def _patient_to_cache_row(p: dict) -> dict:
    name = (p.get("name") or [{}])[0]
    given = name.get("given") or []
    identifier = p.get("identifier") or []
    mrn = next(
        (i.get("value") or "" for i in identifier if "MR" in (i.get("system") or "").upper()),
        None,
    )

    return {
        "fhir_id": p["id"],
        "first_name": given[0] if given else "",
        "last_name": name.get("family") or "",
        "dob": (p.get("birthDate") or "1900-01-01"),
        "gender": p.get("gender") or "",
        "mrn": mrn,
        "phone": (p.get("telecom") or [{}])[0].get("value"),
        "email": next(
            (t.get("value") for t in (p.get("telecom") or []) if t.get("system") == "email"),
            None,
        ),
        "address": _first_address(p.get("address") or []),
        "insurer": None,
        "member_id": None,
        "raw_fhir": p,
    }


def _first_address(addrs: list[dict]) -> dict | None:
    if not addrs:
        return None
    a = addrs[0]
    return {
        "line": a.get("line") or [],
        "city": a.get("city") or "",
        "state": a.get("state") or "",
        "postalCode": a.get("postalCode") or "",
    }


async def _upsert_cache(row: dict) -> None:
    await database.execute(
        """
        INSERT INTO patients (fhir_id, first_name, last_name, dob, gender, mrn,
                              phone, email, address, insurer, member_id, raw_fhir)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb)
        ON CONFLICT (fhir_id) DO UPDATE SET
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            dob = EXCLUDED.dob,
            gender = EXCLUDED.gender,
            mrn = EXCLUDED.mrn,
            phone = EXCLUDED.phone,
            email = EXCLUDED.email,
            address = EXCLUDED.address,
            insurer = EXCLUDED.insurer,
            member_id = EXCLUDED.member_id,
            raw_fhir = EXCLUDED.raw_fhir,
            updated_at = NOW()
        """,
        row["fhir_id"],
        row["first_name"],
        row["last_name"],
        row["dob"],
        row["gender"],
        row["mrn"],
        row["phone"],
        row["email"],
        json.dumps(row["address"]) if row["address"] else None,
        row["insurer"],
        row["member_id"],
        json.dumps(row["raw_fhir"]),
    )


def _public_summary(row: dict) -> dict:
    """Deterministic projection for the agent + UI — no PHI beyond what was requested."""
    return {
        "fhir_id": row["fhir_id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "dob": str(row["dob"]),
        "gender": row["gender"],
        "mrn": row["mrn"],
        "phone": row["phone"],
        "email": row["email"],
        "address": row["address"],
        "insurer": row["insurer"],
        "member_id": row["member_id"],
    }


@function_tool
async def get_patient(fhir_id: str) -> dict | None:
    """Fetch a patient by FHIR ID. Reads from the local cache first, then FHIR
    if the cache misses, and refreshes the cache on every hit. Returns a
    summary dict with patient identity + contact fields, or None if unknown."""
    from fhir_client import get_client, FHIRNotFoundError

    cached = await database.query_one(
        "SELECT * FROM patients WHERE fhir_id = $1", fhir_id
    )
    if cached:
        row = dict(cached)
        await audit.record_patient_read(
            "get_patient", fhir_id, f"cache hit for {row.get('first_name')} {row.get('last_name')}"
        )
        return _public_summary(row)

    try:
        p = get_client().read("Patient", fhir_id)
    except FHIRNotFoundError:
        return None

    row = _patient_to_cache_row(p)
    await _upsert_cache(row)
    await audit.record_patient_read(
        "get_patient", fhir_id, f"FHIR fetch + cache sync for {row['first_name']} {row['last_name']}"
    )
    return _public_summary(row)


@function_tool
async def search_patients_by_name_dob(
    first_name: str, last_name: str, dob: str
) -> list[dict]:
    """Search FHIR for patients matching a given (first) name, family name and
    date of birth (YYYY-MM-DD). Returns a list of patient summaries. Empty list
    means no match."""
    from fhir_client import get_client

    params = {"given": first_name, "family": last_name}
    if dob:
        params["birthdate"] = dob

    results = get_client().search("Patient", params)
    out = []
    for p in results:
        row = _patient_to_cache_row(p)
        await _upsert_cache(row)
        out.append(_public_summary(row))

    await audit.record(
        actor="search_patients_by_name_dob",
        action="SEARCH",
        resource_type="Patient",
        summary=f"searched name={first_name} {last_name} dob={dob} -> {len(out)} hits",
    )
    return out