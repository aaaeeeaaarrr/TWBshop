"""core.whatif — read-only "what would this config change DO?" previews. No writes; computes against the
platform's OWN recorded events (the shadow/web check-ins), so it's safe + self-contained per tenant.

Today: the check-in verdict (grace / early). "If you set grace to 9 min, N of your last M check-ins
reclassify (late→on_time …)." The owner can SEE a config change's effect before applying it — the wizard
feature the owner asked for. More what-ifs (OT cap, AL ladder …) slot in beside this later.
"""
from shared.database import _db
from core.attendance import verdict


def verdict_whatif(org_id, new_grace, new_early, tz="Asia/Phnom_Penh", limit=300) -> dict:
    """Recompute the check-in verdict for the org's last `limit` checked_in events under (new_grace,
    new_early) and compare to each event's CURRENT stored state. READ-ONLY. Returns
    {total, changed, by_transition:{"late→on_time":n,…}, examples:[…]}."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT e.at, e.detail, s.start_dt
                           FROM attendance_events e JOIN shifts s ON s.shift_id = e.shift_id
                           WHERE e.org_id=%s AND e.type='checked_in' AND s.start_dt IS NOT NULL
                           ORDER BY e.at DESC LIMIT %s""", (org_id, int(limit)))
            rows = cur.fetchall()
    total, changed, by_transition, examples, current = 0, 0, {}, [], {}
    for r in rows:
        old_state = (r["detail"] or {}).get("state")
        if not old_state:
            continue
        total += 1
        current[old_state] = current.get(old_state, 0) + 1            # the breakdown as it stands today
        new_state, _late, _early = verdict(r["at"], r["start_dt"], tz, int(new_grace), int(new_early))
        if new_state != old_state:
            changed += 1
            key = "%s→%s" % (old_state, new_state)
            by_transition[key] = by_transition.get(key, 0) + 1
            if len(examples) < 8:
                examples.append({"at": str(r["at"]), "from": old_state, "to": new_state})
    return {"total": total, "changed": changed, "by_transition": by_transition, "examples": examples,
            "current": current}
