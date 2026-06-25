"""Current-truth docs must not cite files that don't exist — the staleness guard.

Extends the MAP.md integrity guard to ALL current-truth docs: if a doc references a `dir/file.py`
(or .ps1/.sh/.json/.md) that was deleted or moved, this FAILS — so a current-truth doc can't silently
describe code that's gone (it would have caught a doc still pointing at a function we deleted today).

EXCLUDED (history-logs — allowed to mention past/removed paths): docs/HISTORY.md,
docs/VERIFICATION_RECORD.md (a stamped session-33 snapshot), and the generated MAP_INDEX.md.

This is the MECHANICAL half of truth-consolidation. The SEMANTIC half — the same fact restated in two
prose places — stays human-adjudicated on purpose: a reliable prose-duplication detector isn't
achievable without false positives, and noise would be worse than the disease.
"""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DENY = {"docs/HISTORY.md", "docs/VERIFICATION_RECORD.md", "MAP_INDEX.md",
        "docs/POSBUSINESS_HARVEST_PLAN.md"}   # cross-repo + forward-looking: cites POSbusiness files + not-yet-built core/* paths
# backtick-quoted, dir-qualified (>=1 slash) path ending in a known extension; optional ::symbol
_REF = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_./-]+\.(?:py|ps1|sh|json|md))(?:::([A-Za-z0-9_]+))?`")


def _current_truth_docs():
    docs = ["CLAUDE.md", "MAP.md"]
    docs += [os.path.relpath(p, ROOT).replace("\\", "/") for p in glob.glob(os.path.join(ROOT, "docs", "*.md"))]
    return [d for d in docs if d not in DENY and os.path.exists(os.path.join(ROOT, d))]


def _symbol_defined(fp, sym):
    with open(fp, encoding="utf-8") as f:
        content = f.read()
    return bool(re.search(r"(?:async def|def|class)\s+%s\b" % re.escape(sym), content)
                or re.search(r"(?m)^\s*%s\s*=" % re.escape(sym), content))


def _violations():
    bad = []
    for d in _current_truth_docs():
        with open(os.path.join(ROOT, d), encoding="utf-8") as f:
            text = f.read()
        for path, sym in sorted(set(_REF.findall(text))):
            fp = os.path.join(ROOT, path)
            if not os.path.exists(fp):
                bad.append((d, "%s (missing file)" % path))
            elif sym and path.endswith(".py") and not _symbol_defined(fp, sym):
                bad.append((d, "%s::%s (symbol gone)" % (path, sym)))
    return bad


def test_current_truth_docs_have_no_stale_file_refs():
    bad = _violations()
    assert not bad, "current-truth docs cite files that don't exist (update the doc):\n" + \
        "\n".join("  %s  ->  %s" % b for b in bad)


if __name__ == "__main__":
    import sys
    docs = _current_truth_docs()
    v = _violations()
    print("scanned %d current-truth docs" % len(docs))
    for d, r in v:
        print("STALE:  %s  ->  %s" % (d, r))
    print("violations: %d" % len(v))
    sys.exit(1 if v else 0)  # usable as a gate (e.g. .githooks/pre-push), mirrors reconcile_facts.py
