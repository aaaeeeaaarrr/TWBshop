"""core.retention — bounded growth for the platform's own bookkeeping tables.

The two age-outs below cover the only unbounded growers among the observability
tables (measured 2026-07-03: core_flip_log ≈ 470 rows/day — one per location PING
while a flip net is on; core_send_ledger ≈ tens/day). core_job_heartbeats is one
UPSERTed row per job (no growth). shadow_comparisons, core_transitions and
gm_alarms are cut-over/audit EVIDENCE — deliberately never aged out here; retiring
them is an owner decision, not hygiene.
"""
from shared.database import _db

# auto-revert reads only the last 50 rows per (org, path); 30 days keeps weeks of
# divergence forensics far beyond that.
FLIP_LOG_KEEP_DAYS = 30
# delivery forensics window — undelivered sends re-raise via the sentinel within
# hours, so 90 days is generous.
SEND_LEDGER_KEEP_DAYS = 90
# senior approval-card coords (A9): swaps pop theirs at the verdict; shift-change cards are
# peek-only through their lifecycle, so age is the terminal for those rows.
APPROVAL_CARDS_KEEP_DAYS = 30


def tidy() -> dict:
    """Age out old bookkeeping rows; returns {table: rows_deleted}. Idempotent."""
    out = {}
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM core_flip_log WHERE at < now() - make_interval(days => %s)",
                (FLIP_LOG_KEEP_DAYS,))
            out["core_flip_log"] = cur.rowcount
            cur.execute(
                "DELETE FROM core_send_ledger WHERE at < now() - make_interval(days => %s)",
                (SEND_LEDGER_KEEP_DAYS,))
            out["core_send_ledger"] = cur.rowcount
    # own transaction: approval_cards self-provisions on the first card, so it may not exist
    # yet — its absence must not roll back the deletes above.
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM approval_cards WHERE sent_at < now() - make_interval(days => %s)",
                    (APPROVAL_CARDS_KEEP_DAYS,))
                out["approval_cards"] = cur.rowcount
    except Exception:
        out["approval_cards"] = 0
    return out
