"""Guard for the truth registry (scripts/facts.py + facts.json + facts_lineage.jsonl).

The accuracy engine, proven to BITE. It is READ-ONLY by construction: every test below either reads the
real registry or builds an in-memory copy — none call set_fact()/append_lineage(), so running the suite
never mutates facts.json or the lineage. That is the zero-new-mistakes property made testable: a checker
that only compares can flag a wrong value but can never write one.

What it locks in:
  - the live seed reconciles clean (a doc drifting from the registry, or config.py changing without the
    registry, turns this red — the cross-doc contradiction class that bit us with "points"/attendance);
  - planted value-drift / doc-drift / bad-pointer are all caught (the guard works);
  - runtime facts are NEVER value-asserted (no prod connection from a checker — by design);
  - every fact has a genesis lineage line (birth cites an independent read — proof, not echo).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import facts  # noqa: E402


# ── the live guard: the real seed must reconcile clean ──────────────────────────────────────────────
def test_seed_reconciles_clean():
    problems = facts.reconcile()
    assert not problems, "facts.json drifted from its sources/docs — fix the doc or the registry:\n" + \
        "\n".join("  [%s] %s -> %s" % (p["kind"], p["key"], p["detail"]) for p in problems)


def test_registry_well_formed():
    for key, f in facts.load().items():
        assert f["source"] in facts.SOURCES, "%s: bad source" % key
        assert f["status"] in facts.STATUSES, "%s: bad status" % key
        for k in ("value", "asserted_on"):
            assert k in f, "%s: missing %s" % (key, k)
        if f["source"] in facts.DERIVABLE:
            assert f.get("locator"), "%s: derivable fact needs a locator" % key


# ── the guard provably bites (each plants a fault in an IN-MEMORY copy; writes nothing) ──────────────
def test_value_drift_is_caught():
    fs = facts.load()
    a_code_key = next(k for k, f in fs.items() if f["source"] in facts.DERIVABLE)
    fs[a_code_key] = dict(fs[a_code_key], value="WRONG-NOT-THE-REAL-VALUE")
    kinds = {(p["kind"], p["key"]) for p in facts.reconcile(fs)}
    assert ("value-drift", a_code_key) in kinds


def test_doc_drift_is_caught():
    fs = facts.load()
    key = next(k for k, f in fs.items() if f.get("mentions"))
    f = dict(fs[key])
    f["mentions"] = [dict(f["mentions"][0], template="STRING_THAT_IS_NOT_IN_ANY_DOC_zzz")]
    fs[key] = f
    assert any(p["kind"] == "doc-drift" and p["key"] == key for p in facts.reconcile(fs))


def test_bad_pointer_is_caught(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "CLAUDE.md").write_text("see {{fact:no_such_fact}} here", encoding="utf-8")
    probs = facts._bad_pointers(facts.load(), str(tmp_path))
    assert any(p["kind"] == "bad-pointer" and p["key"] == "no_such_fact" for p in probs)


def test_known_pointer_is_accepted(tmp_path):
    real_key = next(iter(facts.load()))
    (tmp_path / "docs").mkdir()
    (tmp_path / "CLAUDE.md").write_text("see {{fact:%s}}" % real_key, encoding="utf-8")
    assert facts._bad_pointers(facts.load(), str(tmp_path)) == []


# ── design guarantees ───────────────────────────────────────────────────────────────────────────────
def test_runtime_facts_are_never_value_asserted():
    """A volatile runtime fact must never produce a value-drift — the checker must not reach for prod."""
    for key, f in facts.load().items():
        if f["source"] == "runtime":
            assert f["source"] not in facts.DERIVABLE
            # even a deliberately 'wrong' cached value can't trip value-drift for a runtime fact
            fs = facts.load()
            fs[key] = dict(f, value="obviously-stale-value")
            assert not any(p["kind"] == "value-drift" and p["key"] == key for p in facts.reconcile(fs))


def test_every_fact_has_genesis_lineage():
    for key in facts.load():
        assert facts.lineage_for(key), "%s has no lineage line (birth must cite a real read)" % key


def test_lineage_file_is_valid_jsonl():
    with open(facts.LINEAGE, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if line:
                row = json.loads(line)  # raises if a line is malformed
                assert {"ts", "key", "from", "to", "by", "source", "why"} <= set(row), "line %d missing keys" % i
