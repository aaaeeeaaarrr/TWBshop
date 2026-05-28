# 06 — Evidence and Audit Trail

## The principle

Every finding about a person must have a source. "Seth was late repeatedly" is not a finding. "Seth was reported late by Rath Phal on May 12 (ops_messages id=792273) and by SAM PHARM on March 11 (likely, id=792213), with 'again' used by Met Solina on May 27 (id=792886) indicating supervisors treated this as an established pattern" is a finding.

The system is designed to hold evidence, not just conclusions.

## Three evidence layers

### 1. Physical documents — hiring_assessment_evidence

Paper questionnaires, printed assessments, photos of handwritten answers, or ChatGPT-analyzed scans. Each row stores:

- `file_name` — the actual file (nullable if not yet filed)
- `file_hash` — SHA-256 of the file content (auto-computed when path is known)
- `storage_status` — one of 8 precise values:

| Value | Meaning |
|-------|---------|
| `local_to_owner_phone` | On the owner's phone, not backed up |
| `local_to_pc` | On the owner's PC, not on server or cloud |
| `server` | On the production server |
| `cloud` | Cloud storage (Google Drive, etc.) |
| `telegram_file` | Still in Telegram's CDN as an uploaded file |
| `chatgpt_only` | Uploaded to ChatGPT session; not saved elsewhere |
| `missing` | Known to have existed; cannot be located |
| `deleted` | Deliberately removed after extraction |

`chatgpt_only` is the most fragile status. It means the document was analyzed but not preserved. The content was extracted into `hiring_feedback_points` but the original cannot be re-verified. Upgrade to `local_to_pc` or `server` as soon as practical.

The placeholder rule: never mix NULL `file_name` with real `file_name` rows for the same document set. A NULL row is a placeholder for "photo #1 not yet filed." Update it when you file it — do not add a second row.

### 2. Ops message references — hiring_assessment_message_refs

Links a specific finding to a specific message in `ops_messages`. This is the strongest evidence type because the message is verbatim, timestamped, sender-attributed, and in the DB.

Key columns:
- `ops_message_row_id` — `ops_messages.id` (internal PK)
- `telegram_message_id` — Telegram's own message_id (for display/linking, backfilled from ops_messages)
- `finding_id` — which finding this message supports
- `confidence` — confirmed / likely / inferred
- `notes` — the exact quoted text and the reasoning

The UNIQUE constraint is `(assessment_id, finding_id, chat_id, ops_message_row_id)`. One message can support multiple findings by appearing in multiple rows with different `finding_id` values. This was a deliberate design fix: Met Solina's May 27 message (792886) supports both the no-show finding and the rotating-excuse finding — two separate evidence links, one message.

### 3. Staff identity confirmation — staff_identity_aliases

Not strictly evidence for a finding, but prerequisite to all ops-message evidence. Before any message can be used as evidence, the sender's identity and the subject's identity must be resolved. The alias table stores every confirmed or likely name variant per person.

Confidence levels:
- `confirmed` — direct self-identification, or unambiguous full-name reference by a supervisor
- `likely` — strong match with one plausible alternate interpretation
- `inferred` — probable based on context alone; no direct identification

Evidence linked at `confirmed` confidence level can be stated directly. Evidence at `likely` should be noted with the alternate interpretation. Evidence at `inferred` should be treated as corroborating context only, not a standalone finding.

## The Seth case — a complete example

Seth (Phan Piseth, candidate_id=27, assessment_id=5) is the first person with a fully linked evidence trail:

**Aliases confirmed:**
- "Seth 🫵" (self-introduction, Stock Checks, May 27)
- "Phan Piseth" (same self-introduction)
- "Mr Piseth" (used by all five supervisors: Lina So, Rath Phal, Bart KimHeng, Met Solina, por Khmer Bruce PP)
- "Mr pisey" (SAM PHARM, marked likely — SAM PHARM also reports a different Mr Pisey)
- "Mr Sith" (SAM PHARM, likely typo for Seth, same period)

**6 findings, 12 message refs:**

| finding_id | slug | Key messages |
|-----------|------|-------------|
| 90 | punctuality_gap | 792213 (Mar 11, SAM PHARM, likely), 792273 (May 12, Rath Phal, confirmed) |
| 91 | payback_pattern | 792215 (Mar 13, SAM PHARM), 792256 (Apr 25, Bart KimHeng), 792258 (Apr 27, Lina So), 792264 (May 3, Por) |
| 92 | multi_supervisor_reporting | 792886 (Met Solina, "again" is the key word) |
| 93 | no_show_exam_claim | 792886 (Met Solina, May 27 full no-show), 792905 (Seth's own introduction same day) |
| 94 | rotating_excuse_pattern | 792213 (mom's house), 792258 (no reason, 4pm), 792886 (exams) |
| 95 | management_response_gap | (narrative finding — no single message; documented as pattern) |

Finding 93 and 94 both reference message 792886. This is why the UNIQUE constraint includes `finding_id` — before the fix, only one of these could be stored.

## How to add new evidence

**New ops message ref:**
```python
INSERT INTO hiring_assessment_message_refs
    (assessment_id, finding_id, chat_id, ops_message_row_id, confidence, notes)
VALUES (...)
ON CONFLICT (assessment_id, finding_id, chat_id, ops_message_row_id) DO NOTHING;

-- Then backfill telegram_message_id:
UPDATE hiring_assessment_message_refs mr
SET telegram_message_id = om.message_id
FROM ops_messages om
WHERE mr.chat_id = om.chat_id AND mr.ops_message_row_id = om.id
  AND mr.telegram_message_id IS NULL;
```

**New physical document:**
Insert a row into `hiring_assessment_evidence` with `storage_status` set accurately. Set `file_hash` using `hash_file(path)` from the import script helpers if the file path is known.

**New alias:**
Insert into `staff_identity_aliases` with the correct `confidence` level and a `confirmed_by` reference (ops_messages id, or person who confirmed). Never create an alias at `confirmed` without a specific source.

## Evidence decay

Evidence in `hiring_assessment_evidence` with `storage_status = 'chatgpt_only'` or `'local_to_owner_phone'` is at risk of becoming inaccessible. These statuses should be treated as temporary. Move to `server` or `cloud` and update the row. A finding supported only by ephemeral evidence becomes harder to defend in a formal conversation with the staff member.
