"""CLIENT/BUILDER SEPARATION — structural guard (owner 2026-06-30, after a SHALLOW audit leaked builder
messages onto the client GM bot: I fixed the one file I was shown, not the whole class).

THE LAW (PRODUCT SECURITY & IP + the s58 separation work): a BUILDER/SYSTEM message — digests, alarms,
crashes, watchdogs, monitoring, cut-over readiness — must reach the owner via the MONITOR bot
(shared.monitor_notify / MONITOR_BOT_TOKEN), NEVER via a CLIENT bot token (GM_BOT_TOKEN / BOT_TOKEN).
A CLIENT message (orders, attendance, the manager's own ops notices) goes via the client bot.

WHY THIS TEST EXISTS: the leak was a whole CLASS — standalone cron scripts + a service (morning_report,
collection_watchdog, listener) each POSTing a system message with a CLIENT token. A one-file audit can't
catch a class. This guard makes the class structurally un-shippable: every RAW Telegram POST in the repo
must either use the Monitor channel or be explicitly classified as a legitimate client sender. A NEW
unclassified client-token POST FAILS the suite → forcing whoever adds it to decide builder-vs-client.

SCOPE / honesty: this guards the RAW-POST class (scripts/crons/services — the class that bit us). It cannot
read intent, so it does NOT police the PTB client bots' in-process `context.bot` owner-DMs (gm_bot's
shadow-digest + dead-button were that kind; they're locked by the regression test below + the DRASTIC-CHANGE
protocol in CLAUDE.md). Extend the registries below as the product grows."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Files that ARE the builder/monitor channel — POSTing via the MONITOR token here is correct.
MONITOR_SENDERS = {
    "shared/monitor_notify.py",          # the one shared builder->Monitor helper (notify_monitor)
    "scripts/monitor.py",                # the lane/service watcher (MONITOR_BOT_TOKEN)
    "scripts/monitor_bot.py",            # @TWB_Monitor_bot itself
}

# Files that LEGITIMATELY POST via a CLIENT bot token because the message is genuinely CLIENT-facing
# (NOT a builder/system alarm). Each needs a one-line reason. Adding a file here is a deliberate, reviewed
# classification — that is the whole point of the guard.
CLIENT_TOKEN_SENDERS = {
    "core/automations.py": "client-configured automations dispatch to the client's OWN targets (not a builder alarm)",
    "run_send_historical_photos.py": "manual one-off tool the OWNER runs to re-send a client's historical photos",
}


def _py_files():
    for p in REPO.rglob("*.py"):
        rel = p.relative_to(REPO).as_posix()
        if rel.startswith(("tests/", "archive/")) or "/.venv/" in ("/" + rel):
            continue
        yield rel, p


def test_no_builder_message_via_a_client_token():
    """Every raw api.telegram.org sendMessage must be the Monitor channel OR an allow-listed client sender.
    A new, unclassified raw POST = a potential builder leak → FAIL until it's classified."""
    offenders = []
    for rel, p in _py_files():
        if rel in MONITOR_SENDERS or rel in CLIENT_TOKEN_SENDERS:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if "api.telegram.org/bot" in text and "sendMessage" in text:
            offenders.append(rel)
    assert not offenders, (
        "Raw Telegram sendMessage POST in unclassified file(s): %s\n"
        "CLASSIFY each (owner 2026-06-30 — no system things on a client bot):\n"
        "  • BUILDER/system (digest/alarm/crash/watchdog/monitoring) → route via shared.monitor_notify "
        "(the Monitor bot); do NOT POST with GM_BOT_TOKEN/BOT_TOKEN.\n"
        "  • genuine CLIENT message → add the file to CLIENT_TOKEN_SENDERS in this test WITH a reason."
        % offenders)


def test_the_2026_06_30_leak_fixes_stay_fixed():
    """Regression lock: the 5 senders fixed on 2026-06-30 must keep routing via the Monitor."""
    # the 3 standalone cron/service senders → notify_monitor, never a client token
    for rel in ("scripts/morning_report.py", "run_collection_watchdog.py", "ops_intelligence/listener.py"):
        text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        assert "notify_monitor" in text, "%s must send builder alerts via the Monitor (notify_monitor)" % rel
        assert "GM_BOT_TOKEN" not in text, "%s must NOT send via a client token (GM_BOT_TOKEN)" % rel
    # the 2 gm-process sends → the Monitor route (shadow digest via _monitor_send_sync, dead-button via _alarm)
    gm = (REPO / "gm_bot/bot.py").read_text(encoding="utf-8", errors="replace")
    assert '_monitor_send_sync, "📊 [SHADOW] nightly review' in gm, \
        "the gm shadow digest must route via the Monitor (_monitor_send_sync), not context.bot"
    assert 'await _alarm(context, "dead_button"' in gm, \
        "the gm dead-button alert must route via _alarm (Monitor + sink), not context.bot"
