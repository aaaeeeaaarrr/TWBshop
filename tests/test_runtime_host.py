"""A6 (inert skeleton): the multi-tenant runtime host assembles N independent tenant
Applications in one process — per-tenant handlers + error handler, fail-soft on a bad spec."""
from telegram.ext import CommandHandler

from runtime_host.host import TenantSpec, build_apps


def _registrar_factory(tag, bag):
    async def cmd(update, context):
        pass

    def register(app, org_id):
        app.add_handler(CommandHandler("ping_" + tag, cmd))
        bag.append(org_id)
    return register


def test_two_tenants_two_independent_apps():
    bag = []
    apps, skipped = build_apps([
        TenantSpec("orga", "123:aaa", _registrar_factory("a", bag)),
        TenantSpec("orgb", "456:bbb", _registrar_factory("b", bag)),
    ])
    assert not skipped and [o for o, _ in apps] == ["orga", "orgb"]
    assert bag == ["orga", "orgb"], "each registrar ran against its own app"
    a, b = apps[0][1], apps[1][1]
    assert a is not b and a.bot.token != b.bot.token
    assert a.handlers and b.handlers, "tenant handlers attached"
    assert a.error_handlers and b.error_handlers, "per-tenant crash isolation wired"


def test_bad_tenant_is_skipped_not_fatal():
    def boom(app, org_id):
        raise RuntimeError("typo'd config")
    bag = []
    apps, skipped = build_apps([
        TenantSpec("bad", "123:aaa", boom),
        TenantSpec("good", "456:bbb", _registrar_factory("g", bag)),
    ])
    assert [o for o, _ in apps] == ["good"] and bag == ["good"]
    assert skipped and skipped[0][0] == "bad", "the fleet must not die on one tenant's bad spec"
