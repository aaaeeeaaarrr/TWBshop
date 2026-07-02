"""A9 (2026-07-03): senior approval-card coords (swap / shift-change) persist across a gm
restart — bot_data alone orphans co-seniors' cards, and the future chase ladders (Part C)
need durable coords to re-ping/supersede."""
from shared.database import _db, approval_card_add, approval_cards_get, approval_cards_pop

KIND = "swap"
REF = 987654321


def _cleanup():
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM approval_cards WHERE ref_id=%s", (REF,))
    except Exception:
        pass


def test_add_get_pop_roundtrip():
    _cleanup()
    try:
        approval_card_add(KIND, REF, -100123, 555)
        approval_card_add(KIND, REF, -100124, 556)
        assert approval_cards_get(KIND, REF) == [(-100123, 555), (-100124, 556)]
        assert approval_cards_get(KIND, REF) == [(-100123, 555), (-100124, 556)], "peek must not consume"
        assert approval_cards_pop(KIND, REF) == [(-100123, 555), (-100124, 556)]
        assert approval_cards_pop(KIND, REF) == [], "pop is terminal — the finalize sweep runs once"
        assert approval_cards_get(KIND, REF) == []
    finally:
        _cleanup()


def test_kinds_are_isolated():
    _cleanup()
    try:
        approval_card_add("swap", REF, -1, 1)
        approval_card_add("shift_change", REF, -2, 2)
        assert approval_cards_get("swap", REF) == [(-1, 1)]
        assert approval_cards_pop("shift_change", REF) == [(-2, 2)]
        assert approval_cards_get("swap", REF) == [(-1, 1)], "popping one kind must not touch the other"
    finally:
        _cleanup()


def test_retention_ages_out_stale_cards():
    from core import retention
    _cleanup()
    try:
        approval_card_add(KIND, REF, -9, 9)
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE approval_cards SET sent_at = now() - interval '40 days' "
                            "WHERE ref_id=%s", (REF,))
        counts = retention.tidy()
        assert counts.get("approval_cards", 0) >= 1
        assert approval_cards_get(KIND, REF) == []
    finally:
        _cleanup()
