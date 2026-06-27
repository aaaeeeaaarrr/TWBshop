"""core.onboarding_flow — DISCOVER-CONFIRM staff onboarding (docs/ONBOARDING_DESIGN.md).

The principle: the system DISCOVERS, the owner CONFIRMS. A channel adapter (the bot) calls
record_seen_member() when it sees someone post in a staff group; the owner then confirms each candidate
into a core_staff record (with name/role/expertises/hours) or skips them. Channel-agnostic + org-scoped;
acts on NOTHING live — it builds a NEW tenant's roster (TWB keeps its own staff_registry). Pure data layer;
the Telegram UI + guided BotFather are the adapter, wired next.
"""
import json
import uuid

from shared.database import _db
from core.db import _org_secret_cipher, _ENC_PREFIX

# Sensitive PII columns encrypted AT REST when ORG_SECRET_KEY is set (the W3 gate). TEXT columns only —
# date_of_birth is a DATE column (can't hold a cipher token) + lower-risk, so it stays as-is. Until the key
# is set: plaintext + the same one-time warning the org-secret store uses (graceful, no behaviour change).
# Reads pass legacy plaintext values through untouched; a value the key can no longer decrypt fails safe (None).
_SENSITIVE_PII = {"national_id", "passport_no", "tax_id", "social_security_no", "address", "bank_account"}


def _pii_enc(value):
    if value is None or value == "":
        return value
    c = _org_secret_cipher()
    if not c:
        return value                                      # no key → plaintext (W3 warning lives in init/docs)
    return _ENC_PREFIX + c.encrypt(str(value).encode()).decode()


def _pii_dec(value):
    if not isinstance(value, str) or not value.startswith(_ENC_PREFIX):
        return value                                      # legacy plaintext (or non-string) → as-is
    c = _org_secret_cipher()
    if not c:
        return None                                       # encrypted but key gone → fail safe (never expose)
    try:
        return c.decrypt(value[len(_ENC_PREFIX):].encode()).decode()
    except Exception:
        return None


def _dec_row(row):
    """Decrypt the sensitive PII fields of a core_staff row dict (in place); returns it (or None)."""
    if row:
        for k in _SENSITIVE_PII:
            if k in row:
                row[k] = _pii_dec(row[k])
    return row


# ── discover (the bot feeds these) ───────────────────────────────────────────
def record_seen_member(org_id: str, tg_user_id: int, tg_name: str = None, tg_username: str = None,
                       chat_id: int = None) -> None:
    """The bot saw this person in a staff group → stage them as a pending candidate. Idempotent: re-seeing
    refreshes their name/username but never overturns a confirmed/skipped decision."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO core_onboarding_candidates (org_id, tg_user_id, chat_id, tg_name, tg_username)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (org_id, tg_user_id) DO UPDATE
                     SET tg_name=COALESCE(EXCLUDED.tg_name, core_onboarding_candidates.tg_name),
                         tg_username=COALESCE(EXCLUDED.tg_username, core_onboarding_candidates.tg_username),
                         chat_id=COALESCE(EXCLUDED.chat_id, core_onboarding_candidates.chat_id)""",
                (org_id, tg_user_id, chat_id, tg_name, tg_username))


def list_candidates(org_id: str, status: str = "pending") -> list[dict]:
    """The discovered people awaiting the owner's confirm (the 'I found these — confirm each' list)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM core_onboarding_candidates WHERE org_id=%s AND status=%s "
                        "ORDER BY seen_at", (org_id, status))
            return [dict(r) for r in cur.fetchall()]


# ── confirm (the owner decides, one by one) ──────────────────────────────────
def confirm_candidate(org_id: str, tg_user_id: int, name: str, call_name: str = None, role: str = None,
                      is_senior: bool = False, expertises: list = None, shift_windows: list = None) -> int:
    """Confirm a candidate into a core_staff record (linked to their Telegram id) and mark them confirmed —
    ONE transaction. Idempotent per (org, telegram_id): confirming the same person again updates their row,
    never duplicates. Returns the staff_id."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT consent FROM core_onboarding_candidates WHERE org_id=%s AND tg_user_id=%s",
                        (org_id, tg_user_id))
            row = cur.fetchone()
            consent = bool(row["consent"]) if row and row["consent"] is not None else False
            cur.execute(
                """INSERT INTO core_staff (org_id, name, call_name, role, is_senior, expertises,
                                           shift_windows, telegram_id, consent)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (org_id, telegram_id) WHERE telegram_id IS NOT NULL DO UPDATE
                     SET name=EXCLUDED.name, call_name=EXCLUDED.call_name, role=EXCLUDED.role,
                         is_senior=EXCLUDED.is_senior, expertises=EXCLUDED.expertises,
                         shift_windows=EXCLUDED.shift_windows, consent=EXCLUDED.consent
                   RETURNING staff_id""",
                (org_id, name, call_name, role, is_senior, json.dumps(expertises or []),
                 json.dumps(shift_windows or []), tg_user_id, consent))
            staff_id = cur.fetchone()["staff_id"]
            cur.execute("UPDATE core_onboarding_candidates SET status='confirmed' "
                        "WHERE org_id=%s AND tg_user_id=%s", (org_id, tg_user_id))
            return staff_id


def skip_candidate(org_id: str, tg_user_id: int) -> None:
    """Mark a discovered person as 'not staff' so they drop off the confirm list."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_onboarding_candidates SET status='skipped' "
                        "WHERE org_id=%s AND tg_user_id=%s", (org_id, tg_user_id))


def record_consent(org_id: str, tg_user_id: int, consented: bool) -> None:
    """A staffer answered the consent ask (via /start). Stored on the candidate; carried to their staff
    record at confirm. Also stages them (so a silent staffer who taps the link still becomes a candidate)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_onboarding_candidates SET consent=%s WHERE org_id=%s AND tg_user_id=%s",
                        (bool(consented), org_id, tg_user_id))


# ── manual entry / read ──────────────────────────────────────────────────────
def add_staff_manual(org_id: str, name: str, call_name: str = None, role: str = None, is_senior: bool = False,
                     expertises: list = None, shift_windows: list = None) -> int:
    """Add a staffer by hand (no candidate) — the 'type them in' path."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO core_staff (org_id, name, call_name, role, is_senior, expertises,
                           shift_windows) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING staff_id""",
                        (org_id, name, call_name, role, is_senior, json.dumps(expertises or []),
                         json.dumps(shift_windows or [])))
            return cur.fetchone()["staff_id"]


def list_staff(org_id: str, status: str = "active") -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM core_staff WHERE org_id=%s AND status=%s ORDER BY staff_id",
                        (org_id, status))
            return [_dec_row(dict(r)) for r in cur.fetchall()]


def remove_staff(org_id: str, staff_id: int) -> None:
    """Soft-remove (status='removed') — reversible, keeps history. Scoped to the org."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_staff SET status='removed' WHERE org_id=%s AND staff_id=%s",
                        (org_id, staff_id))


# ── WEB check-in link (token = the staffer's identity for the browser channel) ────────────────────────
def ensure_checkin_token(org_id: str, staff_id: int) -> str | None:
    """Get (or mint) a staffer's web check-in token — the secret link they open to check in. Idempotent."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT checkin_token FROM core_staff WHERE org_id=%s AND staff_id=%s",
                        (org_id, staff_id))
            r = cur.fetchone()
            if not r:
                return None
            if r["checkin_token"]:
                return r["checkin_token"]
            tok = uuid.uuid4().hex
            cur.execute("UPDATE core_staff SET checkin_token=%s WHERE org_id=%s AND staff_id=%s",
                        (tok, org_id, staff_id))
            return tok


def staff_by_checkin_token(token: str) -> dict | None:
    """The active staffer behind a web check-in link (the token alone identifies them + their org)."""
    if not token:
        return None
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM core_staff WHERE checkin_token=%s AND status='active'", (token,))
            r = cur.fetchone()
            return _dec_row(dict(r)) if r else None


def get_staff(org_id: str, staff_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM core_staff WHERE org_id=%s AND staff_id=%s", (org_id, staff_id))
            r = cur.fetchone()
            return _dec_row(dict(r)) if r else None


def update_staff(org_id: str, staff_id: int, name: str, call_name: str = None, role: str = None,
                 is_senior: bool = False, expertises: list = None, shift_windows: list = None) -> None:
    """Update a staffer's editable fields (the wizard edit form supplies all of them). Scoped to the org."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE core_staff SET name=%s, call_name=%s, role=%s, is_senior=%s,
                           expertises=%s, shift_windows=%s WHERE org_id=%s AND staff_id=%s""",
                        (name, call_name, role, is_senior, json.dumps(expertises or []),
                         json.dumps(shift_windows or []), org_id, staff_id))


# ── Universal employee-record (HR profile) fields — a whitelist so the dynamic UPDATE can NEVER touch an
#    arbitrary column. (Identity name/call_name/role/is_senior/skills/hours stay in update_staff above.)
PROFILE_TEXT = ["nationality", "national_id", "passport_no", "gender", "marital_status", "email", "phone",
                "address", "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relation",
                "employee_code", "department", "employment_type", "work_location", "tax_id",
                "social_security_no", "work_permit_no", "contract_type", "indemnity_details", "bank_account",
                "notes", "day_off"]
PROFILE_DATE = ["date_of_birth", "passport_expiry", "start_date", "end_date", "probation_end_date",
                "work_permit_expiry"]
PROFILE_BOOL = ["contract_on_file", "indemnity_enabled", "right_to_work_verified"]
PROFILE_FIELDS = PROFILE_TEXT + PROFILE_DATE + PROFILE_BOOL


def update_staff_profile(org_id: str, staff_id: int, fields: dict) -> None:
    """Set the whitelisted universal HR-profile fields on a core_staff row. Text/date: '' → NULL. Bool:
    truthy → True. Unknown keys are ignored (no arbitrary columns can be written). Scoped to the org."""
    sets, vals = [], []
    for k in PROFILE_TEXT + PROFILE_DATE:
        if k in fields:
            v = (fields.get(k) or "").strip() or None                 # '' → NULL (incl. dates)
            if k in _SENSITIVE_PII:
                v = _pii_enc(v)                                       # encrypt sensitive PII at rest (when keyed)
            sets.append("%s=%%s" % k)
            vals.append(v)
    for k in PROFILE_BOOL:
        if k in fields:
            sets.append("%s=%%s" % k)
            vals.append(bool(fields.get(k)))
    if not sets:
        return
    vals += [org_id, staff_id]
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_staff SET %s WHERE org_id=%%s AND staff_id=%%s" % ", ".join(sets), vals)


# ── GROUPS the bot is in (auto-discovered) + their roles ──────────────────────
GROUP_ROLES = ["staff", "suppliers", "management", "expenses", "reports"]


def record_group(org_id: str, chat_id: int, title: str = None) -> None:
    """The bot saw/was-added-to a group → remember it (refresh the title; keep any assigned role)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO core_org_groups (org_id, chat_id, title) VALUES (%s,%s,%s)
                           ON CONFLICT (org_id, chat_id) DO UPDATE
                             SET title=COALESCE(EXCLUDED.title, core_org_groups.title)""",
                        (org_id, chat_id, title))


def list_groups(org_id: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM core_org_groups WHERE org_id=%s ORDER BY seen_at", (org_id,))
            return [dict(r) for r in cur.fetchall()]


def set_group_role(org_id: str, chat_id: int, role: str) -> None:
    """Tag a group with a role. A role is single-occupancy (one staff group) — assigning it clears any prior
    holder of that role. role='' / not in GROUP_ROLES → unassign."""
    role = role if role in GROUP_ROLES else None
    with _db() as conn:
        with conn.cursor() as cur:
            if role:
                cur.execute("UPDATE core_org_groups SET role=NULL WHERE org_id=%s AND role=%s", (org_id, role))
            cur.execute("UPDATE core_org_groups SET role=%s WHERE org_id=%s AND chat_id=%s",
                        (role, org_id, chat_id))


def group_id_for_role(org_id: str, role: str) -> int | None:
    """The chat_id the owner tagged with this role (e.g. the STAFF group that discover-confirm watches)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT chat_id FROM core_org_groups WHERE org_id=%s AND role=%s LIMIT 1", (org_id, role))
            r = cur.fetchone()
            return r["chat_id"] if r else None
