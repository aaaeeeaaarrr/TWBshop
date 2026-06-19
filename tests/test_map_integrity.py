"""MAP.md integrity — catch the map's drift mechanically (most of it).

MAP.md routes any task to its files/laws/history. A pointer that lies (moved file, relocated logic,
unlisted new file) is worse than no map — it sends you confidently wrong (the 2026-06-19 failure,
automated). This guards the catchable drift:

  1. dead path            — a `path` that doesn't exist                         -> FAIL
  2. relocated logic      — a `path::symbol` whose symbol left the file         -> FAIL  (Fault 3)
  3. unlisted file        — a package .py neither indexed nor MAP-IGNOREd       -> FAIL  (Fault 1)
  4. unmapped package     — a whole code package missing from the map           -> FAIL

CANNOT be caught (stays human, now a tiny surface): a gotcha whose file+symbol still exist but whose
*behaviour* silently changed. Mitigation: gotchas POINT to the law/test that owns the truth (checks 1/2
verify those pointers resolve), so a stale hint is caught when you read the destination. Index only.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, "MAP.md")

# `path` or `path::symbol`, path ending in a known extension.
_TOKEN_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|md|ps1|json|sh))(?:::([A-Za-z0-9_]+))?`")
_PACKAGES = ("gm_bot", "accountant", "stock", "b2b_bot", "hire_bot", "shared", "ops_intelligence")


def _map_text() -> str:
    with open(MAP, encoding="utf-8") as f:
        return f.read()


def _tokens():
    return _TOKEN_RE.findall(_map_text())   # [(path, symbol_or_'')]


def test_map_file_exists():
    assert os.path.exists(MAP), "MAP.md is missing"


def test_every_referenced_path_exists():
    paths = sorted({p for p, _ in _tokens() if "/" in p})   # dir-qualified only (skip gitignored root files)
    assert paths, "MAP.md references no files — parsing broke or the map is empty"
    missing = [p for p in paths if not os.path.exists(os.path.join(ROOT, p))]
    assert not missing, "MAP.md points to files that don't exist — update the map: %s" % missing


def test_every_symbol_anchor_resolves():
    """Fault 3: a `file::symbol` anchor whose symbol is no longer in that file = logic moved out."""
    bad = []
    for path, sym in _tokens():
        if not sym:
            continue
        fp = os.path.join(ROOT, path)
        if not os.path.exists(fp):
            continue   # the path test already flags this
        with open(fp, encoding="utf-8") as f:
            content = f.read()
        defined = (re.search(r"(?:async def|def|class)\s+%s\b" % re.escape(sym), content)
                   or re.search(r"(?m)^\s*%s\s*=" % re.escape(sym), content))
        if not defined:
            bad.append("%s::%s" % (path, sym))
    assert not bad, ("MAP.md anchors symbols that aren't in their file — logic moved, update the map: %s"
                     % bad)


def test_every_package_py_is_indexed_or_ignored():
    """Fault 1: every package .py must appear in MAP.md (an area entry OR the MAP-IGNORE block)."""
    text = _map_text()
    miss = []
    for pkg in _PACKAGES:
        d = os.path.join(ROOT, pkg)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".py") or f == "__init__.py":
                continue
            rel = "%s/%s" % (pkg, f)
            if rel not in text:
                miss.append(rel)
    assert not miss, ("package files neither indexed nor MAP-IGNOREd — add to an area or the "
                      "MAP-IGNORE block: %s" % miss)


def test_every_code_package_is_mapped():
    text = _map_text()
    present = [d for d in _PACKAGES if os.path.isdir(os.path.join(ROOT, d))]
    unmapped = [d for d in present if d not in text]
    assert not unmapped, "code packages with no MAP.md entry — add them: %s" % unmapped
