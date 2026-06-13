"""One-off: stand up the isolated staging database on the existing DO cluster.

Creates `twbshop_staging` (idempotent) and clones the SCHEMA ONLY by running every
`init_*_db()` builder against it — NO prod data is copied (the test harness seeds
synthetic is_test rows). Then diffs prod vs staging column-by-column so historical
schema drift (columns added by hand on prod, not by an init fn) is surfaced, not
assumed away.

prod is touched only to: CREATE DATABASE (isolated, cannot affect defaultdb) and read
information_schema metadata (no row data). Run:  python setup_staging.py
"""
import os
from urllib.parse import urlsplit, urlunsplit

import psycopg2

import config

STAGING_DB = "twbshop_staging"


def staging_url_from(prod_url: str) -> str:
    p = urlsplit(prod_url)
    return urlunsplit((p.scheme, p.netloc, "/" + STAGING_DB, p.query, p.fragment))


def create_db() -> None:
    p = urlsplit(config.DATABASE_URL)
    print(f"[create] cluster={p.hostname} current_db={p.path.lstrip('/')}")
    conn = psycopg2.connect(config.DATABASE_URL)
    conn.autocommit = True  # CREATE DATABASE cannot run inside a txn block
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (STAGING_DB,))
            if cur.fetchone():
                print(f"[create] {STAGING_DB}: already exists — skip")
            else:
                cur.execute(f'CREATE DATABASE "{STAGING_DB}"')
                print(f"[create] {STAGING_DB}: CREATED")
    finally:
        conn.close()


def _columns(url: str) -> dict:
    """{table: {column, ...}} from information_schema for the public schema."""
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema='public' ORDER BY 1,2"
            )
            out: dict = {}
            for t, c in cur.fetchall():
                out.setdefault(t, set()).add(c)
            return out
    finally:
        conn.close()


def clone_schema(staging_url: str) -> None:
    os.environ["TWBSHOP_ENV"] = "staging"
    import shared.database as db
    db._STAGING_DATABASE_URL = staging_url
    db._pool = None  # force the pool to (re)open against staging
    # Defense in depth: refuse to build schema unless we are truly on staging.
    assert STAGING_DB in db.active_database_url(), "not pointed at staging — abort"
    # Canonical order (matches run_bot.py + run_gm_bot.py): core first, and
    # staff_registry BEFORE attendance (init_attendance_db ALTERs staff_registry).
    ordered = [
        "init_db", "init_ops_db", "init_supplier_prices_db",
        "init_gm_db", "init_receipt_clarifications_db", "init_gm_finance_db",
        "init_gm_clarifications_db", "init_gm_lateness_db",
        "init_gm_finance_aliases_db", "init_gm_leave_db", "init_stock_db",
        "init_staff_registry_db", "init_attendance_db",
    ]
    found = {n for n in dir(db) if n.startswith("init_") and n.endswith("_db")}
    inits = [n for n in ordered if n in found] + sorted(found - set(ordered))
    print(f"[clone] running {len(inits)} schema builders against {STAGING_DB}")
    for name in inits:
        getattr(db, name)()
        print(f"[clone]   {name}")
    if hasattr(db, "points_seed_catalogue"):
        db.points_seed_catalogue()
        print("[clone]   points_seed_catalogue")


def diff(prod_url: str, staging_url: str) -> None:
    pc, sc = _columns(prod_url), _columns(staging_url)
    pt, st = set(pc), set(sc)
    print(f"[diff] prod tables={len(pt)} staging tables={len(st)}")
    only_prod = sorted(pt - st)
    only_stg = sorted(st - pt)
    if only_prod:
        print(f"[diff] tables on PROD but NOT staging ({len(only_prod)}): {only_prod}")
    if only_stg:
        print(f"[diff] tables on STAGING but not prod ({len(only_stg)}): {only_stg}")
    col_drift = {}
    for t in sorted(pt & st):
        missing = pc[t] - sc[t]
        if missing:
            col_drift[t] = sorted(missing)
    if col_drift:
        print(f"[diff] COLUMNS on prod missing from staging ({len(col_drift)} tables):")
        for t, cols in col_drift.items():
            print(f"[diff]   {t}: {cols}")
    else:
        print("[diff] no missing columns on shared tables")
    if not only_prod and not col_drift:
        print("[diff] OK — staging schema covers every prod table+column the code builds")


if __name__ == "__main__":
    prod_url = config.DATABASE_URL
    staging_url = staging_url_from(prod_url)
    create_db()
    clone_schema(staging_url)
    diff(prod_url, staging_url)
    print("[done] staging ready. Add to secrets.py:")
    print('       STAGING_DATABASE_URL = "<same as DATABASE_URL but db = ' + STAGING_DB + '>"')
