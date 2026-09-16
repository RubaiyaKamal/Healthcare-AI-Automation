-- ============================================================
-- Healthcare AI — app-db schema (cache/state/audit)
-- Run by docker-entrypoint-initdb.d on first container start
-- ============================================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------
-- patients — local cache of FHIR Patient resources
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patients (
    id              BIGSERIAL PRIMARY KEY,
    fhir_id         TEXT UNIQUE NOT NULL,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    dob             DATE NOT NULL,
    gender          TEXT,
    mrn             TEXT,
    phone           TEXT,
    email           TEXT,
    address         JSONB,
    insurer         TEXT,
    member_id       TEXT,
    raw_fhir        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_patients_name   ON patients (last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_patients_dob    ON patients (dob);
CREATE INDEX IF NOT EXISTS idx_patients_trgm   ON patients USING gin (last_name gin_trgm_ops, first_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_patients_mrn    ON patients (mrn);

-- ------------------------------------------------------------
-- encounters — cached FHIR Encounters
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS encounters (
    id              BIGSERIAL PRIMARY KEY,
    fhir_id         TEXT UNIQUE,
    patient_fhir_id TEXT NOT NULL REFERENCES patients(fhir_id) ON DELETE CASCADE,
    encounter_type  TEXT,
    status          TEXT,
    performed_at    TIMESTAMPTZ,
    raw_fhir        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters (patient_fhir_id);

-- ------------------------------------------------------------
-- audit_log — every data access, HIPAA-style trail
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL PRIMARY KEY,
    actor           TEXT NOT NULL,
    actor_type      TEXT NOT NULL DEFAULT 'user',
    action          TEXT NOT NULL,
    resource_type   TEXT,
    resource_id     TEXT,
    summary         TEXT,
    ip_address      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_actor      ON audit_log (actor);
CREATE INDEX IF NOT EXISTS idx_audit_resource   ON audit_log (resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_created    ON audit_log (created_at);

-- ------------------------------------------------------------
-- eligibility_checks — insurance verification results
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eligibility_checks (
    id              BIGSERIAL PRIMARY KEY,
    patient_fhir_id TEXT NOT NULL REFERENCES patients(fhir_id) ON DELETE CASCADE,
    status          TEXT NOT NULL CHECK (status IN ('Covered', 'Not Covered', 'Needs Prior Auth', 'Unknown')),
    payer           TEXT,
    member_id       TEXT,
    raw_response    JSONB,
    resolved_by     TEXT NOT NULL DEFAULT 'RULE',
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checked_by      TEXT NOT NULL DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_eligibility_patient ON eligibility_checks (patient_fhir_id);
CREATE INDEX IF NOT EXISTS idx_eligibility_checked ON eligibility_checks (checked_at DESC);

-- ------------------------------------------------------------
-- sessions — intake agent conversations
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id              BIGSERIAL PRIMARY KEY,
    session_id      TEXT UNIQUE NOT NULL,
    patient_fhir_id TEXT REFERENCES patients(fhir_id),
    status          TEXT NOT NULL DEFAULT 'active',
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- duplicate_check_log — every duplicate-match decision
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS duplicate_check_log (
    id               BIGSERIAL PRIMARY KEY,
    candidate_id     TEXT NOT NULL,
    candidate_name   TEXT,
    candidate_dob    DATE,
    existing_id      TEXT,
    existing_name    TEXT,
    match_type       TEXT NOT NULL DEFAULT 'NONE',  -- NONE|SQL|FUZZY|LLM_ONLY
    similarity       NUMERIC(6,4),
    ai_decision      TEXT,                          -- none|merge|candidate_new
    ai_reasoning     TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Phase 2 — Revenue Cycle Automation
-- ============================================================

-- ------------------------------------------------------------
-- code_reference — ICD-10-CM / CPT / HCPCS lookup table (seeded once)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS code_reference (
    id          BIGSERIAL PRIMARY KEY,
    system      TEXT NOT NULL,                 -- ICD-10-CM | CPT | HCPCS
    code        TEXT NOT NULL,
    display     TEXT NOT NULL DEFAULT '',
    billable    BOOLEAN NOT NULL DEFAULT TRUE,
    category    TEXT,
    UNIQUE (system, code)
);

CREATE INDEX IF NOT EXISTS idx_code_ref_system ON code_reference (system, code);

-- ------------------------------------------------------------
-- payer_rules — which procedures require prior auth, per payer
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payer_rules (
    id                  BIGSERIAL PRIMARY KEY,
    payer_name          TEXT NOT NULL,
    procedure_code      TEXT NOT NULL,          -- CPT/HCPCS
    procedure_display   TEXT,
    requires_prior_auth BOOLEAN NOT NULL DEFAULT FALSE,
    notes               TEXT,
    UNIQUE (payer_name, procedure_code)
);

-- ------------------------------------------------------------
-- coding_suggestions — audit trail: LLM proposal vs validated result
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS coding_suggestions (
    id               BIGSERIAL PRIMARY KEY,
    patient_fhir_id  TEXT REFERENCES patients(fhir_id) ON DELETE CASCADE,
    encounter_fhir_id TEXT,
    note_text        TEXT,
    suggested_codes  JSONB NOT NULL DEFAULT '[]'::jsonb,
    validated_codes  JSONB,
    accepted_codes   JSONB,
    rejected_codes   JSONB,
    resolved_by      TEXT NOT NULL DEFAULT 'LLM',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- claims — local claim lifecycle state
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claims (
    id                BIGSERIAL PRIMARY KEY,
    claim_id          TEXT UNIQUE NOT NULL,
    patient_fhir_id   TEXT NOT NULL REFERENCES patients(fhir_id) ON DELETE CASCADE,
    encounter_fhir_id TEXT,
    payer             TEXT,
    total_amount      NUMERIC(10,2),
    codes             JSONB NOT NULL DEFAULT '[]'::jsonb,
    status            TEXT NOT NULL DEFAULT 'SUBMITTED',
                      -- DRAFT|SUBMITTED|PENDING|PAID|PARTIALLY_PAID|DENIED|ERROR
    prior_auth_status TEXT,                      -- NONE_REQUIRED|REQUIRED|APPROVED
    balance_due       NUMERIC(10,2) NOT NULL DEFAULT 0,  -- patient responsibility (portal billing)
    raw_claim         JSONB,
    claim_response    JSONB,
    resolved_by       TEXT NOT NULL DEFAULT 'RULE',
    submitted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_claims_patient ON claims (patient_fhir_id);
CREATE INDEX IF NOT EXISTS idx_claims_status  ON claims (status);

-- ------------------------------------------------------------
-- prior_auth_requests — every prior-authorization request
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prior_auth_requests (
    id              BIGSERIAL PRIMARY KEY,
    request_id      TEXT UNIQUE NOT NULL,
    patient_fhir_id TEXT NOT NULL REFERENCES patients(fhir_id) ON DELETE CASCADE,
    payer           TEXT,
    procedure_code  TEXT,
    procedure_display TEXT,
    status          TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
                    -- PENDING_REVIEW|SUBMITTED|APPROVED|DENIED
    narrative       TEXT,
    clinical_note   TEXT,
    resolved_by     TEXT NOT NULL DEFAULT 'RULE',
    submitted_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- denials — denial reasons + suggested fixes per claim
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS denials (
    id            BIGSERIAL PRIMARY KEY,
    claim_id      TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    reason_code   TEXT,
    reason_text   TEXT,
    suggested_fix TEXT,
    fix_status    TEXT NOT NULL DEFAULT 'OPEN',  -- OPEN|RESOLVED
    resolved_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_denials_claim ON denials (claim_id);
CREATE INDEX IF NOT EXISTS idx_denials_status ON denials (fix_status);

-- ============================================================
-- Phase 3 — Chatbots (Site Visitor + Patient Portal)
-- ============================================================

-- ------------------------------------------------------------
-- chat_sessions — every chatbot conversation (site + portal),
-- so patient-portal chats are logged like the rest of the record.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    id               BIGSERIAL PRIMARY KEY,
    session_id       TEXT UNIQUE NOT NULL,
    bot              TEXT NOT NULL,                 -- site | portal
    patient_fhir_id  TEXT REFERENCES patients(fhir_id) ON DELETE CASCADE,
    phase            TEXT NOT NULL DEFAULT 'open',
    messages         JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_patient ON chat_sessions (patient_fhir_id);

-- ------------------------------------------------------------
-- demo_requests — sales leads captured by the site chatbot
-- (name/email/hospital) routed to the sales flow.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS demo_requests (
    id            BIGSERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL,
    hospital      TEXT NOT NULL,
    message       TEXT,
    status        TEXT NOT NULL DEFAULT 'NEW',      -- NEW|CONTACTED|BOOKED|CLOSED
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- appointments — portal "next appointment / reschedule" (#1)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appointments (
    id                BIGSERIAL PRIMARY KEY,
    patient_fhir_id   TEXT NOT NULL REFERENCES patients(fhir_id) ON DELETE CASCADE,
    visit_type        TEXT NOT NULL,
    provider          TEXT,
    location          TEXT,
    start_time        TIMESTAMPTZ NOT NULL,
    end_time          TIMESTAMPTZ,
    status            TEXT NOT NULL DEFAULT 'SCHEDULED',  -- SCHEDULED|CANCELLED|COMPLETED
    prep_instructions TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments (patient_fhir_id, start_time);

-- ------------------------------------------------------------
-- lab_results — portal "are my results ready" (#15); a human
-- notification always fires for ANOMALY/CRITICAL in parallel.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lab_results (
    id               BIGSERIAL PRIMARY KEY,
    patient_fhir_id  TEXT NOT NULL REFERENCES patients(fhir_id) ON DELETE CASCADE,
    lab_name         TEXT NOT NULL,
    result           TEXT,
    reference_range  TEXT,
    status           TEXT NOT NULL DEFAULT 'PENDING',
                    -- PENDING|NORMAL|ANOMALY|CRITICAL
    resulted_at      TIMESTAMPTZ,
    notified         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lab_results_patient ON lab_results (patient_fhir_id);

-- ------------------------------------------------------------
-- medications — portal read-only medication list (#8)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS medications (
    id               BIGSERIAL PRIMARY KEY,
    patient_fhir_id  TEXT NOT NULL REFERENCES patients(fhir_id) ON DELETE CASCADE,
    drug_name        TEXT NOT NULL,
    strength         TEXT,
    instructions     TEXT,
    status           TEXT NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE|DISCONTINUED
    prescribed_at    DATE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_medications_patient ON medications (patient_fhir_id, status);

-- ------------------------------------------------------------
-- appointment_requests — human queue: reschedule/book requests
-- and nurse-line callbacks created by the portal chatbot.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appointment_requests (
    id               BIGSERIAL PRIMARY KEY,
    patient_fhir_id  TEXT NOT NULL REFERENCES patients(fhir_id) ON DELETE CASCADE,
    kind             TEXT NOT NULL,                 -- RESCHEDULE|BOOK|NURSE_CALLBACK
    requested_date   TIMESTAMPTZ,
    notes            TEXT,
    status           TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING|APPROVED|DECLINED|DONE
    resolved_by      TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_appointment_requests_patient ON appointment_requests (patient_fhir_id, status);