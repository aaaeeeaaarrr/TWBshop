"""OBSERVABILITY LAW — structural guard (owner direction 2026-07-02: "everything has logs · all logs get
checked · every escalation/ladder reaches its next step · checks spread through the day").

THE LAW (full text + audit → docs/OBSERVABILITY_LAW.md + docs/OBSERVABILITY_AUDIT_2026-07-02.md):
  T1 (FYI sends):    durable log + delivery-verified + alarm-on-failure.
  T2 (action sends): T1 + a chase ladder + a recorded terminal (decision or auto-expire).
  T3 (schedulers):   every scheduled job/cron/service-loop heartbeats with its OWN declared gap —
                     a dead checker is the ultimate dead-end (the 2026-06-11 cron-daemon incident).

This file makes the law structurally un-shippable to violate (like tests/test_client_builder_separation.py
for the client/builder law): a new gm job without a declared heartbeat gap, a de-wired chokepoint, a cron
that stops beating, or a removed detector FAILS the suite. A law without a guard is a hope."""
from pathlib import Path
import re

REPO = Path(__file__).resolve().parent.parent
BOT = (REPO / "gm_bot" / "bot.py").read_text(encoding="utf-8", errors="replace")


def _body(src: str, marker: str) -> str:
    """The source of one top-level async def, up to the next top-level def."""
    tail = src.split(marker, 1)[1]
    return re.split(r"\n(?:async )?def ", tail, maxsplit=1)[0]


def test_every_registered_gm_job_declares_a_heartbeat_gap():
    """T3: a job_queue registration whose name is missing from _JOB_EXPECTED_GAP_MIN (or a stale dict
    entry for a removed job) fails — nobody can add a scheduled job without declaring its liveness."""
    from gm_bot.bot import _JOB_EXPECTED_GAP_MIN
    registered = set(re.findall(r'name="(gm_[a-z_]+)"', BOT))
    assert registered, "no gm job registrations found — the regex or the registration block moved"
    missing = registered - set(_JOB_EXPECTED_GAP_MIN)
    stale = set(_JOB_EXPECTED_GAP_MIN) - registered
    assert not missing, "gm job(s) registered with NO declared heartbeat gap (add to _JOB_EXPECTED_GAP_MIN): %s" % missing
    assert not stale, "stale _JOB_EXPECTED_GAP_MIN entries for jobs that no longer exist: %s" % stale


def test_heartbeat_listener_is_installed_on_the_job_queue():
    assert "add_listener(_hb_on_job_event" in BOT and "EVENT_JOB_EXECUTED" in BOT, \
        "the APScheduler heartbeat listener is gone — gm jobs would run unmeasured (T3)"


def test_att_send_writes_the_send_ledger():
    """T1: the attendance chokepoint must ledger intent→outcome (incl. the no-target branch)."""
    body = _body(BOT, "async def _att_send(")
    assert "send_ledger.record(" in body and "send_ledger.mark(" in body, \
        "_att_send no longer writes core_send_ledger — proactive sends would go unledgered"
    assert "no_target" in body, "_att_send's unresolvable-target branch must ledger a failed send"


def test_client_alert_chokepoint_is_sink_first():
    """T1 for client-ops owner alerts: durable sink BEFORE the DM, delivered flag after."""
    body = _body(BOT, "async def _client_alert(")
    assert "log_alarm(" in body and "mark_delivered(" in body
    assert body.index("log_alarm(") < body.index("_send_once_retrying("), \
        "_client_alert must persist to the sink BEFORE attempting the DM (sink-first)"


def test_one_shot_alerts_route_through_client_alert():
    """The 2026-07-02 audit's gm dead-ends stay fixed: lost-forever one-shot alerts are sink-backed."""
    assert BOT.count('_client_alert(context, "no_report"') == 2, \
        "missing mid/final report alerts must route via _client_alert (books-missing was lost-forever)"
    assert '_client_alert(context, "sales_anomaly"' in BOT
    assert '_client_alert(\n                    context, "al_escalated"' in BOT, \
        "the AL-ladder escalation DM must route via _client_alert (al_mark_escalated blocks any retry)"


def test_notify_monitor_writes_the_send_ledger():
    text = (REPO / "shared" / "monitor_notify.py").read_text(encoding="utf-8", errors="replace")
    assert "core.sends" in text and "record(" in text and "mark(" in text, \
        "notify_monitor no longer ledgers builder DMs — a dropped Monitor send would vanish again"


def test_error_handler_mirrors_crashes_to_the_sink():
    text = (REPO / "shared" / "error_handler.py").read_text(encoding="utf-8", errors="replace")
    assert "log_alarm" in text and "mark_delivered" in text and "_sink(" in text, \
        "bot crashes must land in gm_alarms (durable, Claude-readable), not only a throttled Monitor DM"


def test_scheduled_scripts_beat():
    """T3: every server-scheduled script + the automations service loop heartbeats."""
    for rel in ("run_collection_watchdog.py", "scripts/morning_report.py",
                "scripts/fetch_report_receipts.py", "run_automations.py", "scripts/anchor_audit.py"):
        text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        assert "core.heartbeat" in text and "beat(" in text, "%s must write a liveness heartbeat" % rel


def test_watchdog_covers_every_active_service_and_the_gm_brain():
    text = (REPO / "run_collection_watchdog.py").read_text(encoding="utf-8", errors="replace")
    for svc in ("twbshop-listener", "twbshop-gm", "twbshop-hire",
                "twbshop-retail", "twbshop-automations", "twbshop-wizard"):
        assert svc in text, "collection watchdog lost liveness coverage of %s" % svc
    assert "core_job_heartbeats" in text, \
        "the watchdog must keep the out-of-process check on the gm brain's own watcher jobs"


def test_sentinel_detector_floor():
    """Removing a detector (or renaming without updating the floor) fails — coverage can only grow."""
    from core import sentinel
    names = {n for n, _ in sentinel.DETECTORS}
    assert names >= {"shadow_stalled", "malformed_checkin", "flip_divergence", "config_health",
                     "undelivered_alarms", "stale_heartbeats", "stuck_sends", "silent_flip_revert",
                     "broken_flows"}, \
        "a sentinel detector was removed — the observability net may not shrink"
    from core import flowcheck
    rule_names = {n for n, _ in flowcheck.RULES}
    assert rule_names >= {"core_session", "shadow_mismatch", "onboarding_candidate"}, \
        "a flowcheck rule was removed — flow coverage may not shrink"


def test_automations_sender_rejects_telegram_not_ok():
    text = (REPO / "core" / "automations.py").read_text(encoding="utf-8", errors="replace")
    assert "raise RuntimeError" in text.split("def token_sender", 1)[1].split("\ndef ", 1)[0], \
        "token_sender must raise on ok:false so a rejected dispatch is retried, not recorded as sent"
