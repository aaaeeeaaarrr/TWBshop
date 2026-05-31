"""pytest bootstrap (repo root).

Loaded by pytest before any test module is imported. Its job: make sure the REAL
config.py is in sys.modules first, so that test_intake.py's
`sys.modules.setdefault("config", <stub>)` becomes a no-op.

Without this, whole-directory collection (`pytest tests/`) is order-dependent: if a
test that stubs `config` is imported before a test that needs the real config, the
stub poisons every later module (ImportError: cannot import name ... from 'config').

On a machine with no secrets.py the real import fails; we leave config unset so the
isolated unit tests that supply their own stub still work.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import config  # noqa: F401  — real config wins; later test stubs become no-ops
except Exception:
    pass
