"""
Seed script — generates synthetic patients (Faker) with insurance/contact
details, uploads them as FHIR Patient resources to the local HAPI sandbox,
then syncs them into the Postgres cache and creates a Coverage resource for
each so demo eligibility checks have real data.

Run: python backend/seed_synthea_data.py [--count 12]
"""

import argparse
import json
import random
import sys
import uuid
from datetime import date, timedelta

from faker import Faker

import config
import database
from fhir_client import FHIRValidationError, get_client

fake = Faker()

FIRST_NAMES = [
    "Maria", "James", "Linda", "Robert", "Patricia", "Michael", "Jennifer",
    "William", "Elizabeth", "David", "Susan", "Joseph", "Karen", "Thomas",
    "Nancy", "Charles", "Lisa", "Christopher", "Sandra", "Daniel",
    "Soo", "Wei", "Rahul", "Priya", "Miguel", "Ana", "Chen", "Linh",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson",
    "Nguyen", "Patel", "Kim", "Singh", "Chen", "Tran",
]

PAYERS = ["Acme Health", "MediBest", "National Care", "BlueCross Demo"]


class _DummyClasses:
    pass


def make_fhir_patient() -> tuple[dict, dict]:
    """Returns (fhir_patient, cache_row) with matching ids."""
    mrn = f"MRN-{uuid.uuid4().hex[:10].upper()}"
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    dob = str(date.today() - timedelta(days=random.randint(20 * 365, 75 * 365)))
    gender = random.choice(["male", "female", "other"])
    phone = fake.phone_number()
    email = fake.ascii_email()
    member_id = f"M{random.randint(10000000, 99999999)}"
    insurer = random.choice(PAYERS)

    addr = fake.street_address()
    city = fake.city()
    state = fake.state_abbr()
    zip_code = fake.zipcode()

    patient = {
        "resourceType": "Patient",
        "name": [{"use": "official", "family": last, "given": [first]}],
        "telecom": [
            {"system": "phone", "value": phone, "use": "mobile"},
            {"system": "email", "value": email},
        ],
        "gender": gender,
        "birthDate": dob,
        "address": [{
            "use": "home",
            "line": [addr],
            "city": city,
            "state": state,
            "postalCode": zip_code,
        }],
        "identifier": [
            {"system": "urn:healthcare:auth:mrn", "value": mrn},
            {"system": "urn:healthcare:auth:member", "value": member_id},
        ],
        "managingOrganization": {"display": insurer},
    }

    cache_row = {
        "fhir_id": None,  # set after FHIR create
        "first_name": first,
        "last_name": last,
        "dob": dob,
        "gender": gender,
        "mrn": mrn,
        "phone": phone,
        "email": email,
        "address": {"line": [addr], "city": city, "state": state, "postalCode": zip_code},
        "insurer": insurer,
        "member_id": member_id,
        "raw_fhir": None,
    }
    return patient, cache_row


def make_coverage(patient_fhir_id: str, insurer: str, member_id: str, seed: int) -> dict:
    """Deterministic-ish (seeded by member_id hash) coverage for demos."""
    h = seed % 10
    if h < 5:
        status, end = "active", "2026-12-31"
        subrogation = False
    elif h < 8:
        status, end = "active", "2026-03-31"
        subrogation = True
    else:
        status, end = "cancelled", "2025-09-30"
        subrogation = False

    return {
        "resourceType": "Coverage",
        "status": status,
        "beneficiary": {"reference": f"Patient/{patient_fhir_id}"},
        "period": {"start": "2025-01-01", "end": end},
        "type": {"coding": [{"system": "urn:healthcare:payer", "code": "PPO", "display": insurer}]},
        "payor": [{"display": insurer}],
        "identifier": [{"system": "urn:healthcare:auth:member", "value": member_id}],
        "subrogation": subrogation,
    }


async def seed(count: int) -> None:
    client = get_client()
    await database.init_pool()

    created, errors = 0, 0
    for _ in range(count):
        patient, cache_row = make_fhir_patient()
        try:
            created_p = client.create(patient)
        except FHIRValidationError as e:
            print(f"[error] FHIR rejected patient: {e}")
            errors += 1
            continue

        fhir_id = created_p.get("id")
        cache_row["fhir_id"] = fhir_id
        cache_row["raw_fhir"] = created_p

        await database.execute(
            """
            INSERT INTO patients (fhir_id, first_name, last_name, dob, gender, mrn,
                                  phone, email, address, insurer, member_id, raw_fhir)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11, $12::jsonb)
            ON CONFLICT (fhir_id) DO NOTHING
            """,
            fhir_id, cache_row["first_name"], cache_row["last_name"], cache_row["dob"],
            cache_row["gender"], cache_row["mrn"], cache_row["phone"], cache_row["email"],
            json.dumps(cache_row["address"]), cache_row["insurer"], cache_row["member_id"],
            json.dumps(cache_row["raw_fhir"]),
        )

        try:
            h = int(uuid.uuid5(uuid.NAMESPACE_DNS, cache_row["member_id"]).hex[-2:], 16)
            coverage = make_coverage(fhir_id, cache_row["insurer"], cache_row["member_id"], h)
            client.create(coverage)
        except Exception as e:
            print(f"[warn] coverage for {fhir_id} failed: {e}")

        created += 1
        print(f"[ok] {fhir_id}  {cache_row['first_name']} {cache_row['last_name']}  "
              f"{cache_row['dob']}  {cache_row['member_id']}")

    print(f"\nDone: {created} patients seeded ({errors} errors).")


def main() -> None:
    p = argparse.ArgumentParser(description="Seed synthetic patients into local HAPI FHIR + app-db.")
    p.add_argument("--count", type=int, default=12, help="how many patients to create")
    args = p.parse_args()

    try:
        import asyncio
        asyncio.run(seed(args.count))
    except Exception as e:
        print(f"\n[fatal] seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()