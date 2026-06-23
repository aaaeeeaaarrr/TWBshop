"""core.onboarding_flow — DISCOVER-CONFIRM staff onboarding (docs/ONBOARDING_DESIGN.md).

The principle: the system DISCOVERS, the owner CONFIRMS. A channel adapter (the bot) calls
record_seen_member() when it sees someone post in a staff group; the owner then confirms each candidate
into a core_staff record (with name/role/expertises/hours) or skips them. Channel-agnostic + org-scoped;
acts on NOTHING live — it builds a NEW tenant's roster (TWB keeps its own staff_registry). Pure data layer;
the Telegram UI + guided BotFather are the adapter, wired next.
"""
import json

from shared.database import _db


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
            return [dict(r) for r in cur.fetchall()]


def remove_staff(org_id: str, staff_id: int) -> None:
    """Soft-remove (status='removed') — reversible, keeps history. Scoped to the org."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_staff SET status='removed' WHERE org_id=%s AND staff_id=%s",
                        (org_id, staff_id))


def get_staff(org_id: str, staff_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM core_staff WHERE org_id=%s AND staff_id=%s", (org_id, staff_id))
            r = cur.fetchone()
            return dict(r) if r else None


def update_staff(org_id: str, staff_id: int, name: str, call_name: str = None, role: str = None,
                 is_senior: bool = False, expertises: list = None, shift_windows: list = None) -> None:
    """Update a staffer's editable fields (the wizard edit form supplies all of them). Scoped to the org."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE core_staff SET name=%s, call_name=%s, role=%s, is_senior=%s,
                           expertises=%s, shift_windows=%s WHERE org_id=%s AND staff_id=%s""",
                        (name, call_name, role, is_senior, json.dumps(expertises or []),
                         json.dumps(shift_windows or []), org_id, staff_id))


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
