"""Onboarding e2e — the Telegram adapter → REAL core → DB chain (staging), mock Telegram ONLY. A poster in
the staff group is staged, listed by /onboard, then confirmed via the inline button into a real core_staff
record. This is the integration the mock-only adapter tests don't cover — the best de-risking of the
(otherwise unvalidated) Telegram onboarding short of a real bot."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import core.db as cdb
from shared.database import _db
import adapters.telegram_onboarding as ob
from core.onboarding_flow import record_group, set_group_role, list_candidates, list_staff

cdb.init_core_db()
ORG = "test_onb_chain"
STAFF_GRP = -100777


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_staff WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_onboarding_candidates WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_org_groups WHERE org_id=%s", (ORG,))


def _poster(uid, name):
    upd = MagicMock()
    upd.effective_chat.id = STAFF_GRP
    upd.effective_chat.type = "group"
    upd.effective_chat.title = "Staff"
    upd.effective_user.is_bot = False
    upd.effective_user.id = uid
    upd.effective_user.full_name = name
    upd.effective_user.username = name.lower()
    return upd


def test_onboarding_chain_real_core():
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        record_group(ORG, STAFF_GRP, "Staff")
        set_group_role(ORG, STAFF_GRP, "staff")
        on_msg, cmd_onboard, on_cb = ob.make_handlers(ORG)[:3]

        asyncio.run(on_msg(_poster(7, "Sok"), None))                     # 1. poster staged (real core write)
        assert any(c["tg_user_id"] == 7 for c in list_candidates(ORG))

        u2 = MagicMock()
        u2.effective_message.reply_text = AsyncMock()
        asyncio.run(cmd_onboard(u2, None))                                # 2. /onboard lists them
        assert "review" in u2.effective_message.reply_text.call_args[0][0].lower()

        cb = MagicMock()                                                  # 3. confirm via the inline button
        cb.callback_query.data = "onb:ok:7"
        cb.callback_query.answer = AsyncMock()
        cb.callback_query.edit_message_text = AsyncMock()
        cb.callback_query.message.reply_text = AsyncMock()
        asyncio.run(on_cb(cb, None))

        assert any(s.get("name") == "Sok" for s in list_staff(ORG))       # 4. now a real core_staff record
    finally:
        _clean()


def test_onboarding_consent_path_real_core():
    """The 'approve a link' path, real core: a silent staffer /starts → staged + consent asked → consents →
    confirmed, and the consent carries to their staff record."""
    from core.tenant_config import set_config
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        set_config(ORG, {"onboarding": {"staff_consent_required": True}})
        on_msg, cmd_onboard, on_cb, cmd_start, on_consent = ob.make_handlers(ORG)

        u = MagicMock()                                                   # 1. silent staffer taps /start
        u.effective_user.is_bot = False
        u.effective_user.id = 9
        u.effective_user.full_name = "Lin"
        u.effective_user.first_name = "Lin"
        u.effective_user.username = "lin"
        u.effective_message.reply_text = AsyncMock()
        asyncio.run(cmd_start(u, None))
        assert any(c["tg_user_id"] == 9 for c in list_candidates(ORG))     # staged
        assert "consent" in u.effective_message.reply_text.call_args[0][0].lower()

        cons = MagicMock()                                                # 2. they consent (real record_consent)
        cons.callback_query.data = "cns:yes"
        cons.callback_query.answer = AsyncMock()
        cons.callback_query.edit_message_text = AsyncMock()
        cons.effective_user.is_bot = False
        cons.effective_user.id = 9
        cons.effective_user.full_name = "Lin"
        cons.effective_user.username = "lin"
        asyncio.run(on_consent(cons, None))

        cb = MagicMock()                                                  # 3. owner confirms
        cb.callback_query.data = "onb:ok:9"
        cb.callback_query.answer = AsyncMock()
        cb.callback_query.edit_message_text = AsyncMock()
        cb.callback_query.message.reply_text = AsyncMock()
        asyncio.run(on_cb(cb, None))

        with _db() as c:                                                  # 4. consent carried to the staff record
            with c.cursor() as cur:
                cur.execute("SELECT consent FROM core_staff WHERE org_id=%s AND telegram_id=9", (ORG,))
                row = cur.fetchone()
        assert row and row["consent"] is True
    finally:
        _clean()


def test_onboarding_skip_path_real_core():
    """Skipping a discovered person, real core: they don't become staff and drop off the pending list."""
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        record_group(ORG, STAFF_GRP, "Staff")
        set_group_role(ORG, STAFF_GRP, "staff")
        on_msg, cmd_onboard, on_cb = ob.make_handlers(ORG)[:3]
        asyncio.run(on_msg(_poster(8, "Dara"), None))
        cb = MagicMock()
        cb.callback_query.data = "onb:skip:8"
        cb.callback_query.answer = AsyncMock()
        cb.callback_query.edit_message_text = AsyncMock()
        cb.callback_query.message.reply_text = AsyncMock()
        asyncio.run(on_cb(cb, None))
        assert not any(s.get("name") == "Dara" for s in list_staff(ORG))      # not staff
        assert not any(c["tg_user_id"] == 8 for c in list_candidates(ORG))    # dropped from pending
    finally:
        _clean()
