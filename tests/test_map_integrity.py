"""MAP.md integrity — the map must never lie (the mechanical half of the map-discipline).

MAP.md routes any task to the files/laws/history that concern it. A pointer to a moved/renamed file
is WORSE than no map — it sends you confidently wrong (the exact 2026-06-19 failure, automated). So
this guards the two dangerous drift modes mechanically:
  1. every dir-qualified path MAP.md references must exist  → no dead pointers;
  2. every top-level code package must be mentioned          → no whole-subsystem omission.

What it CANNOT check (stays human): that a *new file inside an existing area* was added to the map,
or that a ⚠ gotcha is still accurate. ~100% on "no dead pointers + no missing subsystem", not on
"complete + accurate". Index only — never let MAP.md grow into prose.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, "MAP.md")

# A path token = inside backticks, ends in a known extension. We only enforce DIR-QUALIFIED paths
# (contain '/') — that targets the real risk (package/doc files moving) and avoids gitignored
# root files like secrets.py that won't exist on a fresh clone.
_PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|md|ps1|json|sh))`")
_PACKAGES = ("gm_bot", "accountant", "stock", "b2b_bot", "hire_bot", "shared", "ops_intelligence")


def _map_text() -> str:
    with open(MAP, encoding="utf-8") as f:
        return f.read()


def _referenced_paths() -> list[str]:
    return sorted({m for m in _PATH_RE.findall(_map_text()) if "/" in m})


def test_map_file_exists():
    assert os.path.exists(MAP), "MAP.md is missing"


def test_every_referenced_path_exists():
    paths = _referenced_paths()
    assert paths, "MAP.md references no files — parsing broke or the map is empty"
    missing = [p for p in paths if not os.path.exists(os.path.join(ROOT, p))]
    assert not missing, "MAP.md points to files that don't exist — update the map: %s" % missing


def test_every_code_package_is_mapped():
    text = _map_text()
    present = [d for d in _PACKAGES if os.path.isdir(os.path.join(ROOT, d))]
    unmapped = [d for d in present if d not in text]
    assert not unmapped, "code packages with no MAP.md entry — add them: %s" % unmapped
