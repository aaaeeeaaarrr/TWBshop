"""core.exceptions — per-staff EXCEPTIONS / overrides (F1, session 58, 2026-06-28).

Generalises the hard-coded "Tyty / Delis are special" exclusions in the live gm bot into clean, per-staff,
config-driven exceptions on core_staff.exceptions (JSONB). ONE "Exceptions" button per staff row opens a
page to tick these. LEAN by design: default = {} = a normal staffer (nothing shown in the face); an
employment-type PRESET sets a sensible bundle in one tap, then you fine-tune the individual toggles.

⚠ INERT today: this is platform config — the LIVE gm bot still hard-codes Tyty and does NOT read this yet.
Wiring it into the live nudge / group-post / approval-routing paths is a later, deliberate cut-over step
(each toggle = one gate in the live path, proven on staging).

Owner examples this models exactly:
  • Tyty  → preset 'vip_exempt' (fully exempt from time/AL/OT/points + no nudges + nothing posted). One tap.
  • Thyda → no preset; just tick 'no_supervisor_posts' + set AL-approver = Tyty. She's still tracked and
            nudged like everyone — only the Supervisors-group posting + AL approval routing change.
  • Freelancer → preset 'freelancer'.
"""
import json

from shared.database import _db

# Grouped toggles — (key, label, help). Every toggle defaults False (= a normal staffer).
EXCEPTION_GROUPS = [
    {"key": "tracking", "label": "Tracking exemptions",
     "help": "Which attendance & pay rules apply to this person at all.",
     "toggles": [
        ("no_attendance", "Not expected to check in / out",
         "No check-in prompts, no lateness, no no-show — e.g. salaried, freelance, or owner-family."),
        ("no_lateness", "Never penalised for lateness",
         "They may still check in, but late minutes never cost points or pay-back."),
        ("no_payback", "Never owes pay-back time",
         "Missed time never becomes a pay-back debt."),
        ("no_al", "Annual Leave not applicable",
         "No AL balance and no AL requests for this person."),
        ("no_ot", "Overtime not tracked",
         "Extra time is never banked or paid as OT."),
        ("no_points", "Excluded from points / scoring",
         "Their attendance behaviour isn't scored."),
     ]},
    {"key": "notifications", "label": "Notifications & visibility",
     "help": "Who hears about this person's attendance.",
     "toggles": [
        ("no_nudges", "Never nudge or chase",
         "No reminders or follow-ups are sent to them."),
        ("no_supervisor_posts", "Keep off the Supervisors group",
         "Their lateness / leave / sick is never posted to the Supervisors group."),
        ("no_management_posts", "Keep off the Management group",
         "Never posted to the Management group."),
        ("quiet", "No proactive messages at all",
         "The bot never messages them unprompted (they can still use it)."),
     ]},
    {"key": "behaviour", "label": "Pay-back & leave behaviour",
     "help": "Change HOW pay-back / leave works for this person — not just whether a rule applies.",
     "toggles": [
        ("payback_to_al", "Pay-back comes out of Annual Leave",
         "When they owe pay-back time, deduct it from their AL balance instead of asking them to work it "
         "off. They still earn and lose points normally (this only reroutes the pay-back, not the scoring)."),
     ]},
]

# Approval-routing overrides — (key, label, help). Value = a staff_id (who approves), or absent = normal ladder.
APPROVAL_FIELDS = [
    ("al_approver_id", "Annual Leave approved by",
     "Only this person approves their AL, instead of the normal senior ladder."),
    ("leave_approver_id", "Special leave approved by",
     "Only this person approves their special leave."),
    ("swap_approver_id", "Day-off swaps approved by",
     "Only this person approves their day-off swaps."),
]

# Employment-type presets — one pick sets a sensible bundle; fine-tune the toggles after.
PRESETS = {
    "standard":          {},
    "part_time":         {},
    "freelancer":        {"no_attendance": True, "no_payback": True, "no_al": True, "no_ot": True,
                          "no_points": True, "no_nudges": True, "no_supervisor_posts": True},
    "salaried_no_clock": {"no_attendance": True, "no_lateness": True, "no_payback": True},
    "vip_exempt":        {"no_attendance": True, "no_lateness": True, "no_payback": True, "no_al": True,
                          "no_ot": True, "no_points": True, "no_nudges": True,
                          "no_supervisor_posts": True, "quiet": True},
}
PRESET_LABELS = {
    "standard": "Standard staff (no exceptions)",
    "part_time": "Part-time / flexible",
    "freelancer": "Freelancer / contractor",
    "salaried_no_clock": "Salaried — no clock-in",
    "vip_exempt": "Fully exempt (VIP / owner-family)",
}

_TOGGLE_KEYS = [t[0] for g in EXCEPTION_GROUPS for t in g["toggles"]]
_APPROVER_KEYS = [f[0] for f in APPROVAL_FIELDS]


def _clean_exceptions(fields: dict) -> dict:
    """Pure whitelist + coercion (no DB): toggles → store only the True ones; approvers → int (dropped if
    blank/0/non-numeric); _preset → only a known preset; notes → trimmed str (≤500). Unknown keys dropped
    so no arbitrary data can be written. Returns the canonical dict to persist."""
    clean: dict = {}
    for k in _TOGGLE_KEYS:
        if bool(fields.get(k)):
            clean[k] = True
    for k in _APPROVER_KEYS:
        v = fields.get(k)
        if v in (None, "", "0", 0):
            continue
        try:
            clean[k] = int(v)
        except (TypeError, ValueError):
            pass
    if fields.get("_preset") in PRESETS:
        clean["_preset"] = fields["_preset"]
    note = (fields.get("notes") or "").strip()
    if note:
        clean["notes"] = note[:500]
    return clean


def get_exceptions(org_id: str, staff_id: int) -> dict:
    """A staffer's exceptions dict ({} = a normal staffer). Org-scoped."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT exceptions FROM core_staff WHERE org_id=%s AND staff_id=%s",
                        (org_id, staff_id))
            r = cur.fetchone()
    if not r or r["exceptions"] in (None, "", "{}"):
        return {}
    exc = r["exceptions"]
    return exc if isinstance(exc, dict) else json.loads(exc)


def set_exceptions(org_id: str, staff_id: int, fields: dict) -> dict:
    """Whitelist-validate + persist a staffer's exceptions; returns the stored dict. Org-scoped."""
    clean = _clean_exceptions(fields)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_staff SET exceptions=%s WHERE org_id=%s AND staff_id=%s",
                        (json.dumps(clean), org_id, staff_id))
    return clean


def apply_preset(preset: str) -> dict:
    """The exceptions bundle for an employment-type preset (does NOT persist; the caller saves it)."""
    base = dict(PRESETS.get(preset, {}))
    if preset in PRESETS:
        base["_preset"] = preset
    return base


def is_exempt(exc: dict, key: str) -> bool:
    """Pure: is this exception toggle on? Safe on None/{}. The future LIVE wiring calls this at each gate
    (e.g. `if is_exempt(exc, 'no_nudges'): return` before sending a nudge)."""
    return bool((exc or {}).get(key))


def approver_for(exc: dict, kind: str) -> int | None:
    """The override approver staff_id for kind in {'al','leave','swap'}, or None = the normal ladder."""
    return (exc or {}).get("%s_approver_id" % kind)


def summary(exc: dict) -> str:
    """A tiny badge for the staff row — '' for a normal staffer (lean: nothing in the face), else '⚙ N'."""
    n = sum(1 for k in _TOGGLE_KEYS if (exc or {}).get(k)) + \
        sum(1 for k in _APPROVER_KEYS if (exc or {}).get(k))
    return ("⚙ %d" % n) if n else ""
