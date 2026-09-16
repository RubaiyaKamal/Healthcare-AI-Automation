"""
Seed Phase 2 reference data for the revenue cycle demo.

  Common ICD-10-CM / CPT / HCPCS codes into code_reference
  ~15-20 payer prior-auth rules across 4 PAYERS

Run: python seed_rcm_data.py [--force]

Idempotent — safe to run multiple times; skips codes already present.
"""

import argparse
import sys

import audit
import database
import config

PAYERS = ["Acme Health", "MediBest", "National Care", "BlueCross Demo"]

# Common ICD-10-CM diagnostic codes (denominator-coded from SNOMED/FHIR value sets)
ICD10_CODES = [
    # Metabolic / endocrine
    ("ICD10CM", "E11",  "Type 2 diabetes mellitus", "diagnosis", True),
    ("ICD10CM", "E11.9","Type 2 diabetes mellitus without complications", "diagnosis", True),
    ("ICD10CM", "E11.65","Type 2 diabetes with hyperglycemia", "diagnosis", True),
    ("ICD10CM", "E78.5","Hyperlipidemia, unspecified", "diagnosis", True),
    ("ICD10CM", "E03.9","Hypothyroidism, unspecified", "diagnosis", True),
    ("ICD10CM", "E11.22","Type 2 diabetic diabetic nephropathy", "diagnosis", True),
    # Cardiovascular
    ("ICD10CM", "I10",  "Essential (primary) hypertension", "diagnosis", True),
    ("ICD10CM", "I25.11","Atherosclerotic heart disease of native coronary artery", "diagnosis", True),
    ("ICD10CM", "I48.91","Unspecified atrial fibrillation", "diagnosis", True),
    ("ICD10CM", "I50.22","Chronic systolic heart failure, moderate", "diagnosis", True),
    ("ICD10CM", "I73.9","Peripheral vascular disease, unspecified", "diagnosis", True),
    # Respiratory
    ("ICD10CM", "J45.20","Mild intermittent asthma, uncomplicated", "diagnosis", True),
    ("ICD10CM", "J44.1","Chronic obstructive pulmonary disease with acute exacerbation", "diagnosis", True),
    ("ICD10CM", "J06.9","Acute upper respiratory infection, unspecified", "diagnosis", True),
    ("ICD10CM", "J20.9","Acute bronchitis, unspecified", "diagnosis", True),
    # Musculoskeletal
    ("ICD10CM", "M17.11","Primary osteoarthritis, right knee", "diagnosis", True),
    ("ICD10CM", "M54.5","Low back pain", "diagnosis", True),
    ("ICD10CM", "M75.10","Rotator cuff syndrome, unspecified shoulder", "diagnosis", True),
    ("ICD10CM", "M81.0","Age-related osteoporosis without pathological fracture", "diagnosis", True),
    # Neuro / psych
    ("ICD10CM", "F32.1","Major depressive disorder, single episode, moderate", "diagnosis", True),
    ("ICD10CM", "F41.1","Generalized anxiety disorder", "diagnosis", True),
    ("ICD10CM", "G43.909","Migraine, unspecified, not intractable", "diagnosis", True),
    ("ICD10CM", "R51.9","Headache, unspecified", "diagnosis", True),
    # GI
    ("ICD10CM", "K21.0","GERD with esophagitis", "diagnosis", True),
    ("ICD10CM", "K58.9","Irritable bowel syndrome without diarrhea", "diagnosis", True),
    ("ICD10CM", "K80.10","Gallstones with acute cholecystitis, without obstruction", "diagnosis", True),
    # Screening / preventive
    ("ICD10CM", "Z00.00","Encounter for general adult medical examination, abnormal findings unspecified", "screening", True),
    ("ICD10CM", "Z12.11","Encounter for screening for malignant neoplasm of colon", "screening", True),
    ("ICD10CM", "Z12.51","Encounter for screening for malignant neoplasm of cervix", "screening", True),
]

# Common CPT codes — evaluation & management, labs, imaging, procedures
CPT_CODES = [
    ("CPT", "99201", "Office/outpatient visit, new patient, 10 min", "E/M", True),
    ("CPT", "99202", "Office/outpatient visit, new patient, 20 min", "E/M", True),
    ("CPT", "99203", "Office/outpatient visit, new patient, 30 min", "E/M", True),
    ("CPT", "99204", "Office/outpatient visit, new patient, 45 min", "E/M", True),
    ("CPT", "99205", "Office/outpatient visit, new patient, 60 min", "E/M", True),
    ("CPT", "99211", "Office/outpatient visit, established patient, 5 min", "E/M", True),
    ("CPT", "99212", "Office/outpatient visit, established patient, 10 min", "E/M", True),
    ("CPT", "99213", "Office/outpatient visit, established patient, 20 min", "E/M", True),
    ("CPT", "99214", "Office/outpatient visit, established patient, 30 min", "E/M", True),
    ("CPT", "99215", "Office/outpatient visit, established patient, 40 min", "E/M", True),
    ("CPT", "99281", "Emergency dept visit, straightforward", "E/M", True),
    ("CPT", "99282", "Emergency dept visit, low complexity", "E/M", True),
    ("CPT", "99283", "Emergency dept visit, moderate complexity", "E/M", True),
    ("CPT", "99284", "Emergency dept visit, high complexity", "E/M", True),
    ("CPT", "99285", "Emergency dept visit, high severity, life-threatening", "E/M", True),
    # Labs
    ("CPT", "80053", "Comprehensive metabolic panel", "lab", True),
    ("CPT", "80061", "Lipid panel", "lab", True),
    ("CPT", "82947", "Glucose, quantitative", "lab", True),
    ("CPT", "83036", "Hemoglobin A1c", "lab", True),
    ("CPT", "85025", "CBC with differential", "lab", True),
    ("CPT", "80050", "General health panel", "lab", True),
    ("CPT", "84443", "Thyroid stimulating hormone (TSH)", "lab", True),
    ("CPT", "82553", "Creatinine with eGFR", "lab", True),
    ("CPT", "84578", "Uric acid, serum", "lab", True),
    ("CPT", "86762", "Hepatitis B surface antibody, quantitative", "lab", True),
    # Imaging
    ("CPT", "71046", "Chest X-ray, 2 views", "imaging", True),
    ("CPT", "73030", "X-ray shoulder, min 2 views", "imaging", True),
    ("CPT", "73721", "MRI lower extremity joint (knee) without contrast", "imaging", True),
    ("CPT", "74177", "CT abdomen and pelvis with contrast", "imaging", True),
    ("CPT", "70553", "MRI brain with/without contrast", "imaging", True),
    ("CPT", "71260", "CT chest with contrast", "imaging", True),
    ("CPT", "93000", "Electrocardiogram, 12-lead, with interpretation", "procedure", True),
    ("CPT", "93306", "Transthoracic echocardiography, complete", "imaging", True),
    # Procedures
    ("CPT", "29881", "Arthroscopy, knee, surgical; with meniscectomy", "procedure", True),
    ("CPT", "47562", "Laparoscopic cholecystectomy", "procedure", True),
    ("CPT", "43239", "Upper GI endoscopy with biopsy", "procedure", True),
    ("CPT", "96372", "Therapeutic injection, SC or IM", "procedure", True),
    ("CPT", "99195", "Venipuncture (phlebotomy) for specimen collection", "procedure", True),
    ("CPT", "90471", "Immunization administration, first vaccine", "procedure", True),
]

# HCPCS — DME, supplies, select services
HCPCS_CODES = [
    ("HCPCS", "E0110", "Walker, rigid (pick-up), adjustable or fixed height", "DME", True),
    ("HCPCS", "E0630", "Pneumatic compressor, segmental home model", "DME", True),
    ("HCPCS", "E0170", "Crutches, forearm (Lofstrand), adjustable, pair", "DME", True),
    ("HCPCS", "J0585", "Botulinum toxin type A, per unit", "drug", True),
    ("HCPCS", "J3490", "Unclassified drug or biological", "drug", True),
    ("HCPCS", "A4253", "Blood glucose test or reagent strips for home glucose monitor", "supply", True),
    ("HCPCS", "A4256", "Lancets, for use with home glucose monitor, per box of 100", "supply", True),
    ("HCPCS", "G0008", "Administration of influenza virus vaccine", "preventive", True),
    ("HCPCS", "G0010", "Administration of pneumococcal vaccine", "preventive", True),
    ("HCPCS", "S9490", "Diabetes management program, not otherwise classified", "other", True),
    ("HCPCS", "90460", "Immunization administration, first vaccine, with counseling", "procedure", True),
]

# Payer prior-auth rules across 4 PAYERS.
# (payer_name, procedure_code, procedure_display, requires_prior_auth, notes)
PAYER_RULES = [
    # Acme Health — conservative
    ("Acme Health", "73721",  "MRI knee without contrast",    True,  "Prior auth required for all MRI"),
    ("Acme Health", "70553",  "MRI brain w/wo contrast",       True,  "Prior auth required for all MRI"),
    ("Acme Health", "74177",  "CT abdomen/pelvis w/contrast",  True,  "Prior auth required for CT w/ contrast"),
    ("Acme Health", "29881",  "Knee arthroscopy meniscectomy", True,  "Prior auth required for all surgery"),
    ("Acme Health", "47562",  "Laparoscopic cholecystectomy",  True,  "Prior auth required for all surgery"),
    # MediBest — moderate
    ("MediBest", "73721",    "MRI knee without contrast",    False, "Covered — no PA required"),
    ("MediBest", "70553",    "MRI brain w/wo contrast",       True,  "PA required for brain MRI only"),
    ("MediBest", "43239",    "Upper GI endoscopy w/ biopsy", True,  "PA required for endoscopy with biopsy"),
    ("MediBest", "29881",    "Knee arthroscopy meniscectomy", True,  "PA required for surgery"),
    # National Care — liberal
    ("National Care", "73721",  "MRI knee without contrast",  False, "Covered"),
    ("National Care", "70553",  "MRI brain w/wo contrast",     False, "Covered"),
    ("National Care", "29881",  "Knee arthroscopy meniscectomy", True, "PA required for all orthopedic surgery"),
    ("National Care", "47562",  "Laparoscopic cholecystectomy", False, "Covered — no PA"),
    # BlueCross Demo — mixed
    ("BlueCross Demo", "73721",  "MRI knee without contrast",    False, "Covered"),
    ("BlueCross Demo", "70553",  "MRI brain w/wo contrast",       True,  "PA required for brain/spine MRI"),
    ("BlueCross Demo", "29881",  "Knee arthroscopy meniscectomy", True,  "PA required"),
    ("BlueCross Demo", "43239",  "Upper GI endoscopy w/ biopsy", False, "Covered — no PA"),
    ("BlueCross Demo", "93306",  "Transthoracic echocardiography", True, "PA required for echo"),
]


async def _seed_code_reference(codes: list[tuple], *, force: bool = False) -> int:
    count = 0
    for system, code, display, category, billable in codes:
        try:
            await database.execute(
                """
                INSERT INTO code_reference (system, code, display, category, billable)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (system, code) DO NOTHING
                """,
                system, code, display, category, billable,
            )
        except Exception as e:
            if "unique" in str(e).lower() and not force:
                continue
            raise
        count += 1
    return count


async def _seed_payer_rules(*, force: bool = False) -> int:
    count = 0
    for payer, proc_code, proc_display, requires_pa, notes in PAYER_RULES:
        try:
            await database.execute(
                """
                INSERT INTO payer_rules (payer_name, procedure_code, procedure_display,
                                         requires_prior_auth, notes)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (payer_name, procedure_code) DO NOTHING
                """,
                payer, proc_code, proc_display, requires_pa, notes,
            )
        except Exception as e:
            if "unique" in str(e).lower() and not force:
                continue
            raise
        count += 1
    return count


async def seed_rcm_data(*, force: bool = False) -> dict:
    await database.connect()
    codes = ICD10_CODES + CPT_CODES + HCPCS_CODES
    inserted = await _seed_code_reference(codes, force=force)
    rules_inserted = await _seed_payer_rules(force=force)
    summary = {
        "codes_inserted": inserted,
        "payer_rules_inserted": rules_inserted,
        "total_icd10": len(ICD10_CODES),
        "total_cpt": len(CPT_CODES),
        "total_hcpcs": len(HCPCS_CODES),
        "total_payer_rules": len(PAYER_RULES),
    }
    await audit.record(
        actor="seed_rcm_data",
        action="SEED_RCM_DATA",
        resource_type="CodeReference",
        summary=f"codes={inserted}, rules={rules_inserted}",
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="overwrite existing codes")
    args = parser.parse_args()
    result = database.run_sync(seed_rcm_data(force=args.force))
    print(f"Inserted {result['codes_inserted']} new codes, {result['payer_rules_inserted']} new payer rules")
    print(f"Totals on file: ICD-10={result['total_icd10']}, CPT={result['total_cpt']}, HCPCS={result['total_hcpcs']}, rules={result['total_payer_rules']}")