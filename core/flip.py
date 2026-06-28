"""core.flip — the instant-revert NET for cutting a path over to the core engine (C1, self-healing program).

The crux (docs/SELF_HEALING_AND_SHADOW_PROGRAM.md): a NAIVE flip turns the monitoring net OFF — once core
is authoritative there's nothing left to compare it against, so the alarms go dark. This makes a flip SAFE
by construction:

  • a per-(org, path) AUTHORITY FLAG, default OFF → live behaviour is EXACTLY today's until you flip;
  • when ON, `decide()` returns CORE's result but ALSO runs the OLD engine as a shadow-OF-core, records
    every agreement, and AUTO-REVERTS (flag→OFF, lands on the known-good old engine) + signals an alarm the
    instant recent divergence breaches a safety threshold — a flip that misbehaves un-flips ITSELF;
  • one call (`set_authoritative(..., False)`) flips authority back INSTANTLY (manual or auto).

INERT until a live path routes a decision through `decide()` with the flag ON — that wiring IS the flip
step (C2, owner-gated). Everything here is pure/DB + tested; while every flag is OFF (the default) nothing
changes live behaviour. `decide()` and the writes FAIL SAFE to the old engine — they never raise into a
live decision."""
import json  # noqa: F401 (reserved for richer detail payloads)

from shared.database import _db

# The paths a flip can cover, in the safe cut-over order (verdict first = behaviourally a no-op when proven).
PATHS = ("checkin", "recording", "points", "payback", "settle")


def init_flip_db() -> None:
    """Create the flip authority + divergence-log tables (additive, idempotent). Called at C2 wiring /
    startup; tests call it directly. Mirrors the gm_events/gm_alarms self-contained-init pattern."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_flip (
                    org_id        TEXT NOT NULL,
                    path          TEXT NOT NULL,
                    authoritative BOOLEAN NOT NULL DEFAULT FALSE,
                    reason        TEXT,
                    updated_at    TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (org_id, path)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_flip_log (
                    id     BIGSERIAL PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    path   TEXT NOT NULL,
                    at     TIMESTAMPTZ DEFAULT NOW(),
                    agree  BOOLEAN NOT NULL,
                    detail TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_core_flip_log ON core_flip_log (org_id, path, id DESC)")


def is_authoritative(org_id: str, path: str) -> bool:
    """Is core authoritative for this (org, path)? Default FALSE (= the old engine decides, today's
    behaviour). Fail-safe: any error → False (old engine)."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT authoritative FROM core_flip WHERE org_id=%s AND path=%s", (org_id, path))
                r = cur.fetchone()
                return bool(r and r["authoritative"])
    except Exception:
        return False


def set_authoritative(org_id: str, path: str, on: bool, reason: str = "") -> None:
    """Flip authority on/off for (org, path) — the manual flip AND the instant revert. Upsert."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO core_flip (org_id, path, authoritative, reason, updated_at)
                           VALUES (%s,%s,%s,%s,NOW())
                           ON CONFLICT (org_id, path)
                           DO UPDATE SET authoritative=EXCLUDED.authoritative, reason=EXCLUDED.reason,
                                         updated_at=NOW()""",
                        (org_id, path, bool(on), reason))


def record_divergence(org_id: str, path: str, agree: bool, detail: str = "") -> None:
    """Append one core-vs-old comparison while authoritative. BEST-EFFORT — must never break a live decision."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO core_flip_log (org_id, path, agree, detail) VALUES (%s,%s,%s,%s)",
                            (org_id, path, bool(agree), str(detail)[:500]))
    except Exception:
        pass


def recent_divergence(org_id: str, path: str, n: int = 50) -> tuple:
    """(total, disagreements) over the most recent `n` comparisons for (org, path)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT agree FROM core_flip_log WHERE org_id=%s AND path=%s
                           ORDER BY id DESC LIMIT %s""", (org_id, path, n))
            rows = cur.fetchall()
    total = len(rows)
    dis = sum(1 for r in rows if not r["agree"])
    return total, dis


def should_auto_revert(total: int, disagreements: int,
                       min_samples: int = 10, max_disagree_rate: float = 0.1) -> bool:
    """Pure: revert to the OLD engine when we have ENOUGH samples AND divergence is too high. The
    self-healing 'freeze + alarm if risky' law made automatic — a flip that's misbehaving un-flips itself."""
    if total < min_samples:
        return False
    return (disagreements / total) > max_disagree_rate


def decide(org_id: str, path: str, core_result, live_result, eq=None):
    """THE net. Returns (result, auto_reverted: bool).
      • flag OFF → (live_result, False): exactly today's behaviour (the old engine decides).
      • flag ON  → core is authoritative; the OLD engine runs as a shadow-OF-core: record agreement, and if
        recent divergence breaches the safety threshold, AUTO-REVERT (flag OFF) and return live_result so the
        system lands on the known-good engine. The caller alarms when auto_reverted is True.
    Fail-safe: ANY error → (live_result, False) — a flip can never make live worse than today."""
    try:
        if not is_authoritative(org_id, path):
            return live_result, False
        agree = (eq(core_result, live_result) if eq else core_result == live_result)
        record_divergence(org_id, path, agree,
                          "" if agree else "core=%r live=%r" % (core_result, live_result))
        total, dis = recent_divergence(org_id, path)
        if should_auto_revert(total, dis):
            set_authoritative(org_id, path, False, "auto-revert: divergence %d/%d" % (dis, total))
            return live_result, True
        return core_result, False
    except Exception:
        return live_result, False
