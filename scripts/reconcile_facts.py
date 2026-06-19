#!/usr/bin/env python3
"""reconcile_facts.py — run the truth-registry checker, READ-ONLY.

  python scripts/reconcile_facts.py            # reconcile; on a DISPUTED value, auto-print its lineage
  python scripts/reconcile_facts.py explain KEY # value + provenance + full lineage (read before guessing)
  python scripts/reconcile_facts.py list        # every fact + its current value

Writes nothing. On a contradiction it AUTO-SHOWS the fact's lineage ("how we got to this truth") so the
fix is informed by history — that is the structural trigger: lineage surfaces when a value is in dispute,
not when someone happens to feel unsure (confident hallucinations don't feel unsure). Exit 1 if anything
is wrong, 0 if clean — usable in a hook/CI as well as by hand.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facts  # noqa: E402

# Windows console is cp1252; force utf-8 so lineage text (em dashes etc.) never crashes the print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


def main(argv) -> int:
    if argv and argv[0] == "explain":
        if len(argv) < 2:
            print("usage: reconcile_facts.py explain KEY")
            return 2
        print(facts.explain(argv[1]))
        return 0
    if argv and argv[0] == "list":
        for k, f in sorted(facts.load().items()):
            print("%-26s = %-16r [%s/%s]" % (k, f["value"], f["source"], f["status"]))
        return 0

    problems = facts.reconcile()
    if not problems:
        n = len(facts.load())
        print("OK — %d facts reconcile clean (no divergence detected; NOT a claim they are true)." % n)
        return 0

    print("FOUND %d problem(s):\n" % len(problems))
    disputed = set()
    for p in problems:
        print("  [%s] %s -> %s" % (p["kind"], p["key"], p["detail"]))
        if p["kind"] in ("value-drift", "doc-drift"):
            disputed.add(p["key"])
    for key in sorted(disputed):
        print("\n--- lineage of disputed fact: %s ---" % key)
        print(facts.explain(key))
    print("\nA human rules MEANING; the machine only flags. Fix the doc or the registry, then re-run.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
