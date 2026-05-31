"""Tests for shared.database.dedup_keeper — pure keeper-selection for ops_messages
deduplication. No DB access (the pure helper only)."""

from shared.database import dedup_keeper


def test_prefers_referenced_message_id():
    # Group has rows (id=10, mid=1019) and (id=11, mid=511491); 511491 is referenced.
    keeper = dedup_keeper([10, 11], [1019, 511491], prefer={511491})
    assert keeper == 11


def test_falls_back_to_smallest_id_when_none_referenced():
    keeper = dedup_keeper([20, 21], [969, 510928], prefer=set())
    assert keeper == 20


def test_smallest_id_even_when_unordered():
    keeper = dedup_keeper([93, 50, 77], [3, 2, 1], prefer=set())
    assert keeper == 50


def test_preferred_wins_over_smaller_id():
    # The smaller id is 50 (mid 2), but mid 1 is preferred -> keep its row (id 77).
    keeper = dedup_keeper([93, 50, 77], [3, 2, 1], prefer={1})
    assert keeper == 77


def test_first_preferred_match_wins():
    # Two rows preferred -> the first in iteration order is kept.
    keeper = dedup_keeper([10, 11], [1019, 511491], prefer={1019, 511491})
    assert keeper == 10


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except Exception as e:
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    print("\n%d/%d passed" % (len(fns) - failed, len(fns)))
    sys.exit(1 if failed else 0)
