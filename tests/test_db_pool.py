"""A1 (capacity, 2026-07-03): the shared connection pool — thread-safe class, bounded
size, burst waiting, poisoned-connection eviction. The 25-conn managed-PG cap is the
tightest constraint in the whole system (docs/CAPACITY_AND_SCALE.md §1); six always-on
services share ~15 usable connections, so no process may burst unbounded and a broken
connection must never be recycled into the pool.
"""
import os
import threading
import time

import psycopg2.pool
import pytest

import shared.database as db


def test_pool_is_the_thread_safe_class():
    # Threads do DB work today (error-handler sink mirror, monitor notify, hire
    # assessment pipeline) — SimpleConnectionPool is not thread-safe.
    assert isinstance(db._get_pool(), psycopg2.pool.ThreadedConnectionPool)


def test_pool_max_is_bounded_and_env_overridable():
    assert db._POOL_MAX == max(1, int(os.environ.get("TWBSHOP_DB_POOL_MAX", "4")))
    assert 1 <= db._POOL_MAX <= 10, "a per-process cap above 10 defeats the fleet budget"


def test_acquire_waits_for_a_freed_conn_instead_of_failing():
    pool = db._get_pool()
    held = [pool.getconn() for _ in range(db._POOL_MAX)]  # exhaust the pool
    try:
        def free_one():
            time.sleep(0.3)
            pool.putconn(held.pop(0))

        t = threading.Thread(target=free_one)
        t.start()
        # Plain getconn() would raise PoolError instantly here; _acquire must wait.
        conn = db._acquire(pool, timeout_s=3.0)
        pool.putconn(conn)
        t.join()
    finally:
        for c in held:
            pool.putconn(c)


def test_acquire_times_out_when_the_pool_stays_exhausted():
    pool = db._get_pool()
    held = [pool.getconn() for _ in range(db._POOL_MAX)]
    try:
        t0 = time.monotonic()
        with pytest.raises(psycopg2.pool.PoolError):
            db._acquire(pool, timeout_s=0.3)
        assert time.monotonic() - t0 >= 0.25, "must actually wait out the timeout"
    finally:
        for c in held:
            pool.putconn(c)


def test_broken_connection_is_evicted_not_recycled():
    with pytest.raises(ValueError):
        with db._db() as conn:
            conn.close()  # simulate the server link dying mid-use
            raise ValueError("boom")
    # The next checkout must yield a WORKING connection, not the poisoned one.
    with db._db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            assert cur.fetchone()["ok"] == 1


def test_nested_db_contexts_coexist_without_deadlock():
    # shadow hooks open a second connection inside a live write (e.g. shadow_checkout
    # inside att_check_out) — depth-2 nesting must fit inside the per-process cap.
    with db._db() as outer:
        with db._db() as inner:
            assert outer is not inner


def test_headroom_alarm_thresholds():
    from core.sentinel import _headroom_alarm
    assert _headroom_alarm(6, 25) == []
    warn = _headroom_alarm(20, 25)
    assert len(warn) == 1 and warn[0]["severity"] == "warn"
    crit = _headroom_alarm(23, 25)
    assert len(crit) == 1 and crit[0]["severity"] == "critical"
    # warn and critical carry distinct dedupe keys so an escalation re-alarms
    assert warn[0]["key"] != crit[0]["key"]
    assert _headroom_alarm(0, 0) == []  # a null cap must never divide/alarm


def test_headroom_detector_runs_read_only_on_staging():
    from core.sentinel import detect_db_headroom
    alarms = detect_db_headroom("twb", None)
    assert isinstance(alarms, list)  # staging is far below 80% — expect []
