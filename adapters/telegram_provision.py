"""adapters.telegram_provision — the AUTO-CONFIGURE half of guided BotFather setup.

BotFather (bot CREATION) is manual/anti-abuse, so the wizard guides the customer through it; once they
paste the token, THIS verifies it and configures the bot via the Bot API (commands · name · description)
so they don't have to. Telegram-specific → lives in adapters/, never core/. Pure functions; mock-testable.
"""
import asyncio

from telegram import Bot, BotCommand

# The command menu every tenant bot gets (kept minimal; tenants/modules can extend later).
STANDARD_COMMANDS = [
    ("start", "Get started / link me"),
    ("onboard", "Confirm your staff (owner)"),
    ("help", "What I can do"),
]


async def _verify_and_configure(token: str, name: str = None, description: str = None, commands=None) -> dict:
    bot = Bot(token)
    async with bot:                                    # opens/closes the HTTP pool
        me = await bot.get_me()                        # verifies the token + gets the bot's identity
        await bot.set_my_commands([BotCommand(c, d) for c, d in (commands or STANDARD_COMMANDS)])
        if name:
            await bot.set_my_name(name[:64])
        if description:
            await bot.set_my_description(description[:512])
    return {"ok": True, "username": me.username, "id": me.id, "name": me.first_name}


def provision(token: str, name: str = None, description: str = None, commands=None) -> dict:
    """Verify the token + auto-configure the bot. Returns {ok, username, id, name} or {ok: False, error}.
    Synchronous wrapper (the wizard is sync); makes REAL Bot-API calls only when a token is given."""
    if not token:
        return {"ok": False, "error": "no token"}
    try:
        return asyncio.run(_verify_and_configure(token, name, description, commands))
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
