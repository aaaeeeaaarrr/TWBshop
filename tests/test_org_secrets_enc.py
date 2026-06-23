"""core_org_secrets — encryption at rest (Fernet when ORG_SECRET_KEY is set; plaintext + a warning when
not). The wizard's token store; the value must never sit in the DB as plaintext once a key exists."""
import core.db as cdb
from core.db import set_org_secret, get_org_secret, has_org_secret, clear_org_secret
from shared.database import _db

cdb.init_core_db()
ORG = "test_sec"


def _raw(org, key):
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT value FROM core_org_secrets WHERE org_id=%s AND key=%s", (org, key))
            r = cur.fetchone()
            return r["value"] if r else None


def test_encrypted_at_rest_round_trips(monkeypatch):
    from cryptography.fernet import Fernet
    cipher = Fernet(Fernet.generate_key())
    monkeypatch.setattr(cdb, "_org_secret_cipher", lambda: cipher)
    try:
        set_org_secret(ORG, "tok", "12345:SECRET")
        raw = _raw(ORG, "tok")
        assert raw.startswith("enc:") and "12345:SECRET" not in raw     # ciphertext at rest, not the plaintext
        assert get_org_secret(ORG, "tok") == "12345:SECRET"             # decrypts back for the connector
        assert has_org_secret(ORG, "tok") is True
    finally:
        clear_org_secret(ORG, "tok")


def test_plaintext_without_key(monkeypatch):
    monkeypatch.setattr(cdb, "_org_secret_cipher", lambda: None)
    try:
        set_org_secret(ORG, "tok2", "plain")
        assert _raw(ORG, "tok2") == "plain"                            # no key → plaintext (with a logged warning)
        assert get_org_secret(ORG, "tok2") == "plain"
    finally:
        clear_org_secret(ORG, "tok2")


def test_encrypted_value_unreadable_without_key(monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setattr(cdb, "_org_secret_cipher", lambda: Fernet(Fernet.generate_key()))
    set_org_secret(ORG, "tok3", "topsecret")
    try:
        monkeypatch.setattr(cdb, "_org_secret_cipher", lambda: None)   # key lost
        assert get_org_secret(ORG, "tok3") is None                      # fail safe — can't decrypt
    finally:
        clear_org_secret(ORG, "tok3")
