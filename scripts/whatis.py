#!/usr/bin/env python3
"""whatis.py — one call, all map layers: "what's true + where to look" for a topic.

Collapses the MAP.md -> MAP_INDEX.md -> facts.json -> lineage traversal into ONE read-only lookup, so
consulting the truth is cheaper than guessing it (the whole point: lower the cost of the right path
below the cost of recall). Zero LLM tokens to run; reads files only; needs no secrets.py.

  python scripts/whatis.py attendance
  python scripts/whatis.py expense
  python scripts/whatis.py points        # surfaces the "two points systems" don't-confuse gotcha

Prints, in order:
  1. REGISTRY — any seeded fact matching the topic (value + provenance + lineage). The authority on NOW.
  2. MAP area — the curated MAP.md block (entry files, the law to read, the gotcha).
  3. INDEX    — matching MAP_INDEX.md file/symbol lines (capped; grep for the full set).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facts  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

ROOT = facts.ROOT
IDX_CAP = 12


def _matching_facts(topic: str) -> list:
    out = []
    for k, f in sorted(facts.load().items()):
        if topic in (k + " " + str(f.get("note", ""))).lower():
            out.append(k)
    return out


def _map_blocks(topic: str) -> list:
    """The MAP.md '## area' blocks whose header or body mentions the topic."""
    with open(os.path.join(ROOT, "MAP.md"), encoding="utf-8") as fh:
        blocks = re.split(r"(?m)^(?=## )", fh.read())
    return [b.strip() for b in blocks if b.startswith("## ") and topic in b.lower()]


def _index_lines(topic: str) -> list:
    fp = os.path.join(ROOT, "MAP_INDEX.md")
    if not os.path.exists(fp):
        return []
    with open(fp, encoding="utf-8") as fh:
        return [ln.rstrip() for ln in fh if topic in ln.lower()]


def main(argv) -> int:
    if not argv:
        print("usage: whatis.py <topic>   (e.g. attendance, expense, points)")
        return 2
    topic = " ".join(argv).lower()
    fk, blocks, idx = _matching_facts(topic), _map_blocks(topic), _index_lines(topic)

    if not (fk or blocks or idx):
        print("no map/registry hit for %r." % topic)
        print("try: python scripts/reconcile_facts.py list   (known facts) — or open MAP.md for areas.")
        return 1

    if fk:
        print("== REGISTRY (what's true NOW — pull this, don't recall) ==")
        for k in fk:
            print(facts.explain(k))
            print()
    if blocks:
        print("== MAP (where to look) ==")
        for b in blocks:
            print(b + "\n")
    if idx:
        print("== INDEX (files / symbols) ==")
        for line in idx[:IDX_CAP]:
            print(line)
        if len(idx) > IDX_CAP:
            print("  ...(+%d more; grep MAP_INDEX.md)" % (len(idx) - IDX_CAP))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
