-- hiring_assessment_evidence: audit trail of source photos/scans per assessment
-- Idempotent: safe to re-run
--
-- Replaces the source_photos placeholder in hiring_assessments.notes.
-- One row per physical file (photo page, scan, PDF).
-- When assessment photos are uploaded to ChatGPT: record file names here so
-- any finding can be traced back to the exact source material.
--
-- storage_status values (precise — not just "local"):
--   local_to_owner_phone  — on owner's phone gallery, not backed up elsewhere
--   local_to_pc           — on a Windows PC (not yet on server or cloud)
--   server                — on the Linux server at a known path
--   cloud                 — Google Drive, Dropbox, or other cloud link
--   telegram_file         — retrievable via Telegram file_id
--   chatgpt_only          — was uploaded to ChatGPT, not saved anywhere else (least durable)
--   missing               — filename recorded but file not located on any device
--   deleted               — was stored, now gone
--
-- Placeholder rule: if an assessment has a placeholder row (file_name IS NULL),
-- UPDATE that row to become photo #1 when the real file is identified.
-- Never leave a NULL file_name row alongside rows that have real file_names.

CREATE TABLE IF NOT EXISTS hiring_assessment_evidence (
    id                   SERIAL PRIMARY KEY,
    assessment_id        INTEGER NOT NULL REFERENCES hiring_assessments(id),
    evidence_type        TEXT NOT NULL DEFAULT 'photo'
        CHECK (evidence_type IN ('photo', 'scan', 'pdf', 'note', 'other')),
    file_name            TEXT,
    file_path_or_url     TEXT,
    page_or_photo_number INTEGER,
    description          TEXT,
    -- SHA-256 of the file at time of import; fill automatically when file is available
    file_hash            TEXT,
    storage_status       TEXT NOT NULL DEFAULT 'missing'
        CHECK (storage_status IN (
            'local_to_owner_phone', 'local_to_pc', 'server', 'cloud',
            'telegram_file', 'chatgpt_only', 'missing', 'deleted'
        )),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hiring_assessment_evidence_assessment
    ON hiring_assessment_evidence (assessment_id);

-- Idempotent column additions for tables created before this migration version
ALTER TABLE hiring_assessment_evidence
    ADD COLUMN IF NOT EXISTS file_hash TEXT;

-- Expand storage_status CHECK to precise values (drop and recreate — no ALTER CONSTRAINT in PG)
ALTER TABLE hiring_assessment_evidence
    DROP CONSTRAINT IF EXISTS hiring_assessment_evidence_storage_status_check;
ALTER TABLE hiring_assessment_evidence
    ADD CONSTRAINT hiring_assessment_evidence_storage_status_check
        CHECK (storage_status IN (
            'local_to_owner_phone', 'local_to_pc', 'server', 'cloud',
            'telegram_file', 'chatgpt_only', 'missing', 'deleted'
        ));
