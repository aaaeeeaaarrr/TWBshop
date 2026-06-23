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
            cur.execute(
                """INSERT INTO core_staff (org_id, name, call_name, role, is_senior, expertises,
                                           shift_windows, telegram_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (org_id, telegram_id) WHERE telegram_id IS NOT NULL DO UPDATE
                     SET name=EXCLUDED.name, call_name=EXCLUDED.call_name, role=EXCLUDED.role,
                         is_senior=EXCLUDED.is_senior, expertises=EXCLUDED.expertises,
                         shift_windows=EXCLUDED.shift_windows
                   RETURNING staff_id""",
                (org_id, name, call_name, role, is_senior, json.dumps(expertises or []),
                 json.dumps(shift_windows or []), tg_user_id))
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
