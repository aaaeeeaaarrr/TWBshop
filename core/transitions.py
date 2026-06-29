"""core.transitions — the universal OLD-vs-NEW comparison log for cut-overs.

Owner law (2026-06-29): "keep older data in notes, that way you can compare everything if the transitions
went well, not only AL, every tiny bit of transition." Every transition (a flip, an exemption gate, a
reroute) records ONE note: what the OLD path would have done vs what the NEW path did — so each cut-over
is provable by comparison, never trusted on its own word. Generalises the check-in flip's `core_flip_log`
(core-vs-old per check-in) to ALL transitions.

Org-scoped, append-only, BEST-EFFORT (a logging failure must NEVER break a live flow). Read with
recent()/summary() to compare; Claude + the morning agent read it to confirm a transition is clean.
"""
import json

from shared.database import _db


def init_transitions_db() -> None:
    """Create the comparison-log table (additive, idempotent). Called at gm startup; tests call it directly."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_transitions (
                    id      BIGSERIAL PRIMARY KEY,
                    org_id  TEXT NOT NULL,
                    kind    TEXT NOT NULL,        -- 'checkin' | 'exempt:no_attendance' | 'route:al_approver' | …
                    key     TEXT,                 -- the subject (staff_id, request id, …)
                    old_val TEXT,                 -- what the OLD path would have done (str / JSON)
                    new_val TEXT,                 -- what the NEW path did
                    matched BOOLEAN,              -- old == new (NULL when not a same-shape equality: a reroute/suppress)
                    detail  TEXT,
                    at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_core_transitions ON core_transitions (org_id, kind, id DESC)")


def _enc(v):
    if v is None:
        return None
    return json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v)


def note(org_id, kind, key, old, new, matched=None, detail: str = "") -> None:
    """Append one OLD-vs-NEW comparison note. BEST-EFFORT — never raises into a live flow. `old`/`new` are
    stringified (JSON for dict/list). Pass `matched`=True/False for a parity check (old==new); leave None
    for a reroute/suppression where the two aren't a same-shape equality (the note IS the record)."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO core_transitions (org_id, kind, key, old_val, new_val, matched, detail)
                               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                            (org_id, kind, None if key is None else str(key),
                             _enc(old), _enc(new), matched, str(detail)[:500]))
    except Exception:
        pass


def recent(org_id, kind=None, n: int = 50) -> list:
    """The most recent comparison notes (newest first), optionally filtered to one kind."""
    with _db() as conn:
        with conn.cursor() as cur:
            if kind:
                cur.execute("""SELECT * FROM core_transitions WHERE org_id=%s AND kind=%s
                               ORDER BY id DESC LIMIT %s""", (org_id, kind, int(n)))
            else:
                cur.execute("""SELECT * FROM core_transitions WHERE org_id=%s ORDER BY id DESC LIMIT %s""",
                            (org_id, int(n)))
            return cur.fetchall()


def summary(org_id, kind=None) -> dict:
    """{total, matched, mismatched, uncomparable} for a kind (or all) — the one-glance 'did the transitions
    go well?' answer. mismatched > 0 on a parity transition = investigate."""
    rows = recent(org_id, kind, n=10 ** 7)
    total = len(rows)
    matched = sum(1 for r in rows if r["matched"] is True)
    mismatched = sum(1 for r in rows if r["matched"] is False)
    return {"total": total, "matched": matched, "mismatched": mismatched,
            "uncomparable": total - matched - mismatched}
