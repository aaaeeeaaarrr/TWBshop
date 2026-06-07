"""Flow-state engine — the foundation under every real attendance ladder (H1, session 28).

Problem it solves: the /test shell keeps step+picks in context.user_data (RAM), so a GM
restart mid-flow (and the GM is restarted often) would drop a staff member halfway through
booking AL — dead buttons, stuck. Production ladders persist every step to the DB instead;
on the next tap/message the handler reloads and RESUMES.

This module is the PURE part (TTLs, merge, expiry math) — unit-tested. The read/write lives
in shared.database (flow_save / flow_load / flow_patch / flow_clear), one row per uid.

Design rules (match the locked spec):
- ONE active flow per uid ("one text-wait at a time, last intention wins") — a new flow
  replaces the old.
- Everything has a TTL. Button-only steps get DEFAULT_TTL_MIN; a step that is WAITING ON
  TYPED TEXT gets the shorter TEXT_WAIT_TTL_MIN (the 30-min rule). Expired = treated as gone
  → the next message just opens the main menu, never a dead half-flow.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

DEFAULT_TTL_MIN = 120     # button-driven step: generous (someone wanders off mid-pick)
TEXT_WAIT_TTL_MIN = 30    # waiting on a typed reason/answer: the locked 30-min window


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_expiry(ttl_min: int, now: datetime | None = None) -> str:
    return ((now or now_utc()) + timedelta(minutes=ttl_min)).isoformat()


def is_expired(expires_iso: str | None, now: datetime | None = None) -> bool:
    if not expires_iso:
        return True
    try:
        exp = datetime.fromisoformat(expires_iso)
    except (ValueError, TypeError):
        return True
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return (now or now_utc()) >= exp


def merge_data(old: dict | None, patch: dict | None) -> dict:
    """Shallow-merge accumulated flow picks. A key set to None in `patch` REMOVES it
    (lets a step undo an earlier pick); other keys overwrite."""
    out = dict(old or {})
    for k, v in (patch or {}).items():
        if v is None:
            out.pop(k, None)
        else:
            out[k] = v
    return out


def ttl_for(step_is_text_wait: bool) -> int:
    return TEXT_WAIT_TTL_MIN if step_is_text_wait else DEFAULT_TTL_MIN
