"""Pytest session setup — DB safety.

Owner (2026-06-16): every test run must use the ISOLATED staging database, NEVER prod.

Root cause this fixes: `shared.database` defaults `TWBSHOP_ENV` to "prod" (so the live payroll DB),
which meant a forgotten env var let the suite seed/mutate production — the `ZZ_*` test-staff that
leaked into prod and tripped the live watchdog. We FORCE staging here, before `shared.database`
lazily builds its connection pool (it reads the env at first `_db()` call, not at import), so no test
can ever touch prod again.

Production services are unaffected: this file is loaded ONLY under pytest. The runtime default in
`shared.database` is left as "prod" on purpose so the live bots need no change.

If `STAGING_DATABASE_URL` is unset, DB access raises loudly — the correct fail-safe (never silently
fall back to prod).
"""
import os

os.environ["TWBSHOP_ENV"] = "staging"
