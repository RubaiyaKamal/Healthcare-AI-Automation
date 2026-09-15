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