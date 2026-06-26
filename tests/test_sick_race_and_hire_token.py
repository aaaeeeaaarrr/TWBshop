"""s55 LIVE-prep fixes (code prepared + proven on staging; the DEPLOY is PARKED for the owner's quiet window).

  • SICK-RACE — the own-sick double-book race is closed by making flow_clear an ATOMIC CLAIM (delete-and-return),
    the same flip-first cure the rest of the system uses: a racing typed-reason and the 30-min auto-resolve
    can't both pass it, so the payback/sick case is booked exactly once.
  • HIRE-TOK — the hire-bot session token mints via os.urandom, independent of the stdlib `secrets` module that
    the repo's secrets.py shadows (which made token_urlsafe AttributeError under run_hire_bot, blocking intake).
"""
import shared.database as db


def test_flow_clear_is_an_atomic_claim():
    uid = 990000001                                  # throwaway test uid (not a real telegram id)
    db.flow_clear(uid)                               # ensure clean
    db.flow_save(uid, "att_pending", "armed", {"flow": "sick_me", "date": "2026-06-26"})
    try:
        assert db.flow_clear(uid) == uid             # the first caller WINS the claim → it books
        assert db.flow_clear(uid) is None            # the race loser gets nothing → it won't double-book
    finally:
        db.flow_clear(uid)


def test_hire_mint_token_avoids_the_shadowed_secrets_module():
    from hire_bot.sessions import _mint_token
    a, b = _mint_token(), _mint_token()
    assert isinstance(a, str) and len(a) >= 20 and "=" not in a and a != b   # urlsafe, unpadded, random
