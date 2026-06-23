"""Wizard Stage 1 — the READ-ONLY config viewer: badge logic is grounded in reality, the page renders the
badged config + the catalog of possibilities, and it stays read-only (no form/POST). Staging DB."""
import core.db as cdb
from wizard.app import create_app
from wizard.status import status_for

cdb.init_core_db()   # ensure the orgs table exists so get_config('twb') reads (empty → DEFAULTS)


def test_status_badges_are_grounded():
    # the ONE live knob today is the AL ladder; the rest of attendance = shadow; other domains = planned
    assert status_for("categories.attendance.approvals.al") == "LIVE"
    assert status_for("categories.attendance.approvals.al.reping_hours") == "LIVE"
    assert status_for("categories.attendance.verdict.grace_min") == "SHADOW"
    assert status_for("categories.attendance.points.catalogue") == "SHADOW"
    assert status_for("categories.attendance.approvals.sick") == "PLANNED"   # only 'al' is wired live
    assert status_for("categories.accountant") == "PLANNED"
    assert status_for("categories.accountant.whatever") == "PLANNED"


def test_viewer_renders_config_and_catalog():
    c = create_app("twb").test_client()
    r = c.get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "grace_min" in body and "approvals" in body          # current config is shown …
    assert "LIVE" in body and "SHADOW" in body and "PLANNED" in body   # … badged
    assert "accountant" in body and "Fingerprint" in body and "Packages" in body  # the menu + integrations
    assert "<form" not in body.lower()                          # Stage 1 is strictly read-only


def test_healthz():
    assert create_app().test_client().get("/healthz").status_code == 200
