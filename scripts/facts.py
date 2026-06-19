#!/usr/bin/env python3
"""facts.py — the truth registry: one home per machine-knowable fact, + its lineage.

WHY (2026-06-20, session 48): the "points" mix-up showed the disease = one fact living in 2+ places
that DRIFT apart. This is the structural fix agreed in docs/SIMPLIFICATION_STRATEGY.md
("DUPLICATION DETECTOR"). Two artifacts:

  - facts.json            THE ONE HOME. Each fact = value + source + locator + asserted_on + status.
  - facts_lineage.jsonl   append-only "how we got to each truth" (PAST-tense; never asserts NOW).

SAFETY — zero new mistakes BY CONSTRUCTION (this is the whole point):
  - This module's checker (reconcile) only ever ASSERTS: it reads a REAL source and COMPARES. It never
    GENERATES or overwrites a doc. A read-only checker can FLAG a wrong value; it can never launder one
    into every doc (the failure a generator would add). Prefer the op that *cannot* introduce error.
  - The ONLY writers are append_lineage() (append-only) and set_fact() (the one home). The guard test
    (tests/test_facts_reconcile.py) calls NEITHER — it is pure read + compare.
  - Facts the machine can't read infallibly are NOT value-asserted: a `runtime` flag points to a live
    check + carries a freshness stamp (no prod connection from a checker); a `human` decision/status is
    flagged and protected only by cross-doc agreement. We never ask the machine to judge MEANING.
  - "consistent ≠ correct": a green reconcile means "no divergence detected", NEVER "facts are true".
    Each fact's birth is a lineage line citing the independent read it came from (Rule 2: proof≠echo).

source types:
  config  — a NAME = literal in config.py        (read by AST; no import → no secrets.py coupling)
  code    — a NAME = literal in any other .py     (read by AST: deterministic, infallible)
  runtime — a live flag (e.g. attendance_live in the DB). Value NOT asserted here, only freshness +
            a `check` pointing at the real read. The most accurate doc for a volatile fact is the
            command to check it, not a cached number.
  human   — a decision/status with no machine source; protected ONLY by cross-doc `mentions` agreement.

MONEY RULE (HIGH-RISK — keeps wrong-at-birth harmless): a live balance / payroll / price VALUE NEVER enters as a
cached `human` fact (no source to self-verify → it could be authoritatively wrong on money). Money is `runtime`
(point to the live DB read, freshness-flagged) or it stays OUT. Derived `config`/`code` money constants are fine
(they self-verify against the source every run). See docs/SIMPLIFICATION_STRATEGY.md → "PIN — money never cached".

Layered with the maps: MAP.md (where) · MAP_INDEX.md (what exists) · facts.json head (what's true NOW)
· facts_lineage.jsonl (how it got true). The lineage is consulted on a CONTRADICTION (a structural
trigger), not on felt uncertainty — confident hallucinations don't feel uncertain. See explain().
"""
import ast
import json
import os
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "facts.json")
LINEAGE = os.path.join(ROOT, "facts_lineage.jsonl")

SOURCES = {"config", "code", "runtime", "human"}
STATUSES = {"live", "superseded", "disputed"}
DERIVABLE = {"config", "code"}  # the infallibly-readable kinds


# ── load / save ───────────────────────────────────────────────────────────────────────────────────
def load(path=REGISTRY) -> dict:
    """The registry as {key: fact}. Never raises on a missing file (returns {})."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("facts", {})


def _save(facts: dict, path=REGISTRY):
    """Write the one home (sorted, LF). Only set_fact() calls this — never a test."""
    blob = {
        "_doc": "THE ONE HOME for machine-knowable facts (truth-consolidation). Edit a fact HERE; every "
                "other mention is a pointer checked against this by tests/test_facts_reconcile.py. "
                "A human adjudicates MEANING; machines only compare values. See scripts/facts.py.",
        "_schema": "value · source(config|code|runtime|human) · locator(path::NAME) · asserted_on(YYYY-MM-DD) "
                   "· status(live|superseded|disputed) · [mentions:[{file,template}]] · [freshness_days] · [check] · [note]",
        "facts": dict(sorted(facts.items())),
    }
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(blob, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ── the infallible readers (deterministic; never execute the target) ────────────────────────────────
def _read_literal(locator: str):
    """`path::NAME` → the module-level literal NAME in that .py, via AST (handles `X = v` and `X: T = v`
    and unary-minus). Never imports/executes the file, so it needs no secrets.py and has no side effects."""
    path, _, name = locator.partition("::")
    fp = os.path.join(ROOT, path)
    with open(fp, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        target = None
        if isinstance(node, ast.Assign):
            target = next((t.id for t in node.targets if isinstance(t, ast.Name) and t.id == name), None)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            target = name
        if target and node.value is not None:
            return ast.literal_eval(node.value)
    raise KeyError("%s not found as a module-level literal in %s" % (name, path))


def derive(fact: dict):
    """The real, current value of a derivable fact (config/code). Raises for runtime/human (by design —
    those have no infallible machine source, so we never fabricate one)."""
    if fact["source"] not in DERIVABLE:
        raise ValueError("source %r is not derivable (runtime/human are not value-asserted)" % fact["source"])
    return _read_literal(fact["locator"])


def _render(fact: dict, mention: dict) -> str:
    """The exact substring a doc must contain for this mention (template with {value}; default str(value))."""
    return mention.get("template", "{value}").format(value=fact["value"])


# ── the reconciler — READ-ONLY. Flags; never fixes. The accuracy engine. ────────────────────────────
def reconcile(facts: dict = None, doc_root: str = ROOT) -> list:
    """Return a list of problem dicts {kind,key,detail}. WRITES NOTHING.

    kinds:
      schema       — a fact is malformed (missing key / bad source / bad status)
      value-drift  — a config/code fact's cached value != the REAL source right now (DISPUTED)
      doc-drift    — a doc no longer contains a registered mention of the fact (DISPUTED)
      stale        — a runtime fact's freshness window has lapsed (verify it live; not 'wrong')
      bad-pointer  — a {{fact:KEY}} token in a doc names a key that isn't in the registry
    """
    if facts is None:
        facts = load()
    problems = []
    today = date.today()

    for key, fact in sorted(facts.items()):
        # schema
        miss = [k for k in ("value", "source", "status", "asserted_on") if k not in fact]
        if miss:
            problems.append({"kind": "schema", "key": key, "detail": "missing %s" % ", ".join(miss)})
            continue
        if fact["source"] not in SOURCES:
            problems.append({"kind": "schema", "key": key, "detail": "bad source %r" % fact["source"]})
        if fact["status"] not in STATUSES:
            problems.append({"kind": "schema", "key": key, "detail": "bad status %r" % fact["status"]})

        # value-drift (config/code): the real source must still equal the cached value
        if fact["source"] in DERIVABLE:
            if not fact.get("locator"):
                problems.append({"kind": "schema", "key": key, "detail": "derivable fact needs a locator"})
            else:
                try:
                    real = derive(fact)
                except Exception as e:  # noqa: BLE001 — a missing locator IS the finding
                    problems.append({"kind": "value-drift", "key": key,
                                     "detail": "can't read %s (%s)" % (fact["locator"], e)})
                else:
                    if real != fact["value"]:
                        problems.append({"kind": "value-drift", "key": key,
                                         "detail": "registry=%r but %s=%r" % (fact["value"], fact["locator"], real)})

        # doc-drift: every registered mention must be present verbatim
        for m in fact.get("mentions", []):
            fp = os.path.join(doc_root, m["file"])
            want = _render(fact, m)
            if not os.path.exists(fp):
                problems.append({"kind": "doc-drift", "key": key, "detail": "mention file missing: %s" % m["file"]})
                continue
            with open(fp, encoding="utf-8") as f:
                if want not in f.read():
                    problems.append({"kind": "doc-drift", "key": key,
                                     "detail": "%s no longer contains %r" % (m["file"], want)})

        # stale (runtime): freshness only — never a prod hit
        if fact["source"] == "runtime" and fact.get("freshness_days"):
            try:
                age = (today - datetime.strptime(fact["asserted_on"], "%Y-%m-%d").date()).days
                if age > fact["freshness_days"]:
                    problems.append({"kind": "stale", "key": key,
                                     "detail": "asserted %sd ago (>%s); verify live: %s"
                                               % (age, fact["freshness_days"], fact.get("check", "?"))})
            except ValueError:
                problems.append({"kind": "schema", "key": key, "detail": "bad asserted_on date"})

    problems += _bad_pointers(facts, doc_root)
    return problems


def _bad_pointers(facts: dict, doc_root: str) -> list:
    """A {{fact:KEY}} token anywhere in a current-truth doc must resolve to a known key (fail loud, not blank)."""
    import glob
    import re
    out = []
    tok = re.compile(r"\{\{fact:([A-Za-z0-9_]+)\}\}")
    docs = ["CLAUDE.md", "MAP.md"] + [os.path.relpath(p, doc_root).replace("\\", "/")
                                      for p in glob.glob(os.path.join(doc_root, "docs", "*.md"))]
    for d in docs:
        fp = os.path.join(doc_root, d)
        if not os.path.exists(fp):
            continue
        with open(fp, encoding="utf-8") as f:
            for k in set(tok.findall(f.read())):
                if k not in facts:
                    out.append({"kind": "bad-pointer", "key": k, "detail": "{{fact:%s}} in %s — no such fact" % (k, d)})
    return out


# ── lineage — append-only, past-tense ("how we got to this truth") ──────────────────────────────────
def append_lineage(key, frm, to, by, source, why, path=LINEAGE):
    """Append ONE immutable line. Appends never collide on merge (each line independent) — unlike a
    hand-edited status line. This is the only history writer; it never rewrites a prior line."""
    line = {"ts": date.today().isoformat(), "key": key, "from": frm, "to": to,
            "by": by, "source": source, "why": why}
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def lineage_for(key, path=LINEAGE) -> list:
    """Every past transition of one fact, oldest→newest. Read-only."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                row = json.loads(ln)
                if row.get("key") == key:
                    out.append(row)
    return out


# ── the one value-writer (manual/CLI; never a test) ─────────────────────────────────────────────────
def set_fact(key, value, *, source, locator=None, by, why, mentions=None, asserted_on=None, **extra):
    """Update the ONE home + append the lineage edge (old→new). New-trumps-old by construction: there is
    no second live copy to disagree with. The old value isn't deleted — it lives in the lineage."""
    facts = load()
    old = facts.get(key, {}).get("value")
    fact = {"value": value, "source": source, "status": "live",
            "asserted_on": asserted_on or date.today().isoformat()}
    if locator:
        fact["locator"] = locator
    if mentions:
        fact["mentions"] = mentions
    fact.update(extra)
    facts[key] = fact
    _save(facts)
    append_lineage(key, old, value, by, source if not locator else "%s:%s" % (source, locator), why)
    return fact


# ── explain — the "structural trigger" reader: call this instead of guessing ────────────────────────
def explain(key) -> str:
    """Current value + provenance + full lineage for one fact. This is what you read when a CONTRADICTION
    fires (or before restating a seeded fact) so you don't hallucinate a value we already superseded."""
    facts = load()
    f = facts.get(key)
    if not f:
        return "no such fact: %s (known: %s)" % (key, ", ".join(sorted(facts)) or "none")
    lines = ["%s = %r  [%s, %s, asserted %s]" % (key, f["value"], f["source"], f["status"], f["asserted_on"])]
    if f.get("locator"):
        lines.append("  source: %s" % f["locator"])
    if f.get("check"):
        lines.append("  verify live: %s" % f["check"])
    hist = lineage_for(key)
    lines.append("  lineage (%d):" % len(hist))
    for h in hist:
        lines.append("    %s  %r -> %r  (%s) -- %s" % (h["ts"], h["from"], h["to"], h["by"], h["why"]))
    return "\n".join(lines)
