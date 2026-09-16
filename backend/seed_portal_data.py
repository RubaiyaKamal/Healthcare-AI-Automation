"""
Seed Phase 3 chatbot data — appointments, lab results, medications, and a
patient-responsibility balance for every patient in the app-db cache, so the
Patient Portal Chatbot demo has something to surface.

Run: python seed_portal_data.py [--force]

Idempotent: a patient is skipped once they already have any of these rows,
unless --force is passed (which deletes and recreates that patient's portal
data).
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone

import database
import config

VISIT_TYPES = [
    ("Annual physical", "physical", "Dr. Aisha Khan"),
    ("Diabetes follow-up", "follow-up", "Dr. James Osei"),
    ("General checkup", "checkup", "Dr. Priya Nair"),
    ("Lab draw", "lab", "Lab Center"),
    ("Knee MRI", "imaging", "Imaging Dept"),
    ("Cardiology consult", "specialist", "Dr. Marcus Chen"),
]

MEDS = [
    ("Metformin", "500 mg", "Take twice daily with meals"),
    ("Lisinopril", "10 mg", "Take once daily in the morning"),
    ("Atorvastatin", "20 mg", "Take once daily in the evening"),
    ("Levothyroxine", "75 mcg", "Take once daily, 30 min before breakfast"),
    ("Albuterol inhaler", "90 mcg", "2 puffs as needed for shortness of breath"),
    ("Sertraline", "50 mg", "Take once daily"),
]

LABS = [
    ("HbA1c", "5.6 %", "4.0–5.6 %"),
    ("Lipid panel", "in range", "per report"),
    ("CBC", "within normal limits", "per report"),
    ("Comprehensive metabolic panel", "within normal limits", "per report"),
]


def _seed(patient_fhir_id: str, *, force: bool = False) -> None:
    has = database.query_one(
        """
        SELECT (SELECT COUNT(*) FROM appointments a WHERE a.patient_fhir_id = $1) +
               (SELECT COUNT(*) FROM lab_results l WHERE l.patient_fhir_id = $1) +
               (SELECT COUNT(*) FROM medications m WHERE m.patient_fhir_id = $1) AS n
        """,
        patient_fhir_id,
    )
    if has["n"] and not force:
        return

    if force:
        database.execute("DELETE FROM lab_results WHERE patient_fhir_id = $1", patient_fhir_id)
        database.execute("DELETE FROM medications WHERE patient_fhir_id = $1", patient_fhir_id)
        database.execute("DELETE FROM appointments WHERE patient_fhir_id = $1", patient_fhir_id)
        database.execute("DELETE FROM appointment_requests WHERE patient_fhir_id = $1", patient_fhir_id)

    h = int(uuid.uuid5(uuid.NAMESPACE_DNS, patient_fhir_id).hex[-4:], 16)
    now = datetime.now(timezone.utc)

    # --- 1 upcoming appointment (varies per patient) ------------------------
    visit_type, prep_key, provider = VISIT_TYPES[h % len(VISIT_TYPES)]
    days_ahead = 2 + (h % 9)
    start = now.replace(hour=9 + h % 8, minute=0, second=0, microsecond=0).replace(
        day=now.day + days_ahead
    )
    locs = {"Annual physical": "Clinic A — 2nd Floor", "General checkup": "Clinic A — 2nd Floor",
            "Diabetes follow-up": "Clinic B", "Lab draw": "Phlebotomy — 1st Floor",
            "Knee MRI": "Imaging Wing", "Cardiology consult": "Building 3, Suite 210"}
    database.execute(
        """
        INSERT INTO appointments (patient_fhir_id, visit_type, provider, location,
                                  start_time, end_time, status, prep_instructions)
        VALUES ($1, $2, $3, $4, $5, $6, 'SCHEDULED', $7)
        """,
        patient_fhir_id, visit_type, provider, locs.get(visit_type, "Main Campus"),
        start, start.replace(minute=45), prep_key + ": see prep_instructions map",
    )

    # --- labs: 2 done (normal / flagged) + 1 pending ------------------------
    # Roughly 1 in 4 patients gets a flagged (ANOMALY/CRITICAL) result so the
    # chatbot's safety path is easy to demo.
    flagged = "CRITICAL" if h % 4 == 0 else ("ANOMALY" if h % 4 == 1 else "NORMAL")
    r1 = LABS[h % len(LABS)]
    r2 = LABS[(h + 1) % len(LABS)]
    database.execute(
        """
        INSERT INTO lab_results (patient_fhir_id, lab_name, result, reference_range,
                                 status, resulted_at, notified)
        VALUES ($1, $2, $3, $4, $5, $6, $6 IS NOT NULL)
        """,
        patient_fhir_id, r1[0], r1[1], r1[2], "NORMAL", now.replace(hour=0, minute=5),
    )
    database.execute(
        """
        INSERT INTO lab_results (patient_fhir_id, lab_name, result, reference_range,
                                 status, resulted_at, notified)
        VALUES ($1, $2, $3, $4, $5, $6, FALSE)
        """,
        patient_fhir_id, r2[0], r2[1], r2[2], flagged, now.replace(day=now.day - 1, hour=23),
    )
    database.execute(
        """
        INSERT INTO lab_results (patient_fhir_id, lab_name, status)
        VALUES ($1, $2, 'PENDING')
        """,
        patient_fhir_id, "TSH (thyroid panel)",
    )

    # --- medications --------------------------------------------------------
    m1, m2 = MEDS[h % len(MEDS)], MEDS[(h + 1) % len(MEDS)]
    for drug, strength, instr in (m1, m2):
        database.execute(
            """
            INSERT INTO medications (patient_fhir_id, drug_name, strength,
                                     instructions, status, prescribed_at)
            VALUES ($1, $2, $3, $4, 'ACTIVE', CURRENT_DATE - 60)
            """,
            patient_fhir_id, drug, strength, instr,
        )

    # --- billing balance (reuse claims if present, else create one) ---------
    existing = database.query_one(
        "SELECT claim_id, status, total_amount, payer FROM claims WHERE patient_fhir_id = $1 LIMIT 1",
        patient_fhir_id,
    )
    if existing:
        due = round(40.0 + (h % 20) * 12.5, 2)
        database.execute(
            "UPDATE claims SET balance_due = $2 WHERE claim_id = $1", existing["claim_id"], due
        )
    else:
        payer = ["Acme Health", "MediBest", "National Care", "BlueCross Demo"][h % 4]
        amount = round(120.0 + (h % 30) * 10.0, 2)
        due = round(amount * 0.2, 2)
        database.execute(
            """
            INSERT INTO claims (claim_id, patient_fhir_id, payer, total_amount,
                                codes, status, prior_auth_status, balance_due, submitted_at)
            VALUES ($1, $2, $3, $4, '[]'::jsonb, 'SUBMITTED', 'NONE_REQUIRED', $5, $6)
            """,
            f"CLM-PORTAL-{uuid.uuid4().hex[:8].upper()}", patient_fhir_id, payer,
            amount, due, now.replace(day=now.day - 3),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="recreate portal data per patient")
    args = parser.parse_args()

    async def run():
        await database.init_pool()
        patients = await database.query("SELECT fhir_id FROM patients ORDER BY fhir_id")
        for p in patients:
            _seed(p["fhir_id"], force=args.force)
        print(f"Seeded portal chatbot data for {len(patients)} patients.")

    try:
        import asyncio
        asyncio.run(run())
    except Exception as e:
        print(f"\n[fatal] portal seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()