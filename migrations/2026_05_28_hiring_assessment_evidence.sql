-- hiring_assessment_evidence: audit trail of source photos/scans per assessment
-- Idempotent: safe to re-run
--
-- Replaces the source_photos placeholder in hiring_assessments.notes.
-- One row per physical file (photo page, scan, PDF).
-- When assessment photos are uploaded to ChatGPT: record file names here so
-- any finding can be traced back to the exact source material.

CREATE TABLE IF NOT EXISTS hiring_assessment_evidence (
    id                   SERIAL PRIMARY KEY,
    assessment_id        INTEGER NOT NULL REFERENCES hiring_assessments(id),
    evidence_type        TEXT NOT NULL DEFAULT 'photo'
        CHECK (evidence_type IN ('photo', 'scan', 'pdf', 'note', 'other')),
    file_name            TEXT,
    file_path_or_url     TEXT,
    page_or_photo_number INTEGER,
    description          TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hiring_assessment_evidence_assessment
    ON hiring_assessment_evidence (assessment_id);
