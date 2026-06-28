"""core.parallel_shadow — run the SAME real check-in history through SEVERAL configs at once (a lean,
few-first parallel shadow) and report what each would change vs today. Reuses core.whatif.verdict_whatif
(READ-ONLY, per-tenant, against the platform's OWN recorded events).

This is the seed of the full parallel-shadow harness (Phase 3 of the self-healing program): the dashboard's
"config-diff preview" killer feature — "shops like yours / your own last month: grace 9 would reclassify 4
check-ins" — and the basis for guardrail-mining + auto-tuned defaults later. Start with a FEW meaningful
configs (NOT brute force); grow when real clients justify it."""
from core.whatif import verdict_whatif

# A small, MEANINGFUL default set (the grace values shops actually weigh) — not a brute-force sweep.
DEFAULT_GRACE = (3, 5, 7, 9, 11)


def verdict_matrix(org_id, grace_values=DEFAULT_GRACE, early=5, tz="Asia/Phnom_Penh", limit=300) -> list:
    """For each grace value, how would the org's recent check-ins reclassify vs today? Returns
    [{grace, early, total, changed, by_transition}], newest real data, READ-ONLY. Few-first + lean."""
    out = []
    for g in grace_values:
        wi = verdict_whatif(org_id, g, early, tz=tz, limit=limit)
        out.append({"grace": g, "early": early, "total": wi["total"], "changed": wi["changed"],
                    "by_transition": wi["by_transition"]})
    return out


def summary_lines(matrix) -> list:
    """Human lines for a script / dashboard: 'grace  9 (early 5): 4/300 reclassify — late→on_time 4'."""
    lines = []
    for m in matrix:
        tr = ", ".join("%s %d" % (k, v) for k, v in sorted(m["by_transition"].items())) or "no change"
        lines.append("grace %2d (early %d): %d/%d reclassify — %s"
                     % (m["grace"], m["early"], m["changed"], m["total"], tr))
    return lines
