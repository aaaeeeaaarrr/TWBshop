"""STRUCTURAL GUARD (2026-07-03; closes the 2026-06-14 ledger item): every DB
connection in the repo flows through shared.database (the pool via _db(), or
raw_connect()), which enforce the fail-closed TWBSHOP_ENV switch. A NEW raw
psycopg2.connect( anywhere else would silently bypass staging isolation AND the
per-process connection budget — this test fails the suite on it.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The sanctioned raw sites: the chokepoint itself, and the cross-database bootstrap
# tool that CREATES the staging DB (inherently needs explicit URLs for two clusters).
ALLOWED = {"shared/database.py", "setup_staging.py"}

_RAW = re.compile(r"psycopg2\.connect\(|from\s+psycopg2\s+import\s+.*\bconnect\b")


def test_no_raw_psycopg2_connect_outside_shared_database():
    me = Path(__file__).resolve()
    bad = []
    for p in REPO.rglob("*.py"):
        rel = p.relative_to(REPO).as_posix()
        if rel in ALLOWED or p.resolve() == me or rel.startswith(("archive/", "venv/", ".venv/")):
            continue
        if _RAW.search(p.read_text(encoding="utf-8", errors="replace")):
            bad.append(rel)
    assert not bad, (
        "raw psycopg2.connect( outside shared.database — bypasses the TWBSHOP_ENV "
        "fail-closed switch and the pool budget; use raw_connect() or _db(): %s" % bad)
