"""core — the new channel-agnostic, multi-tenant management PLATFORM (the product foundation).

This package is built per docs/PLATFORM_VISION.md + docs/ATTENDANCE_DOMAIN_MODEL.md. It runs ENTIRELY
PARALLEL to the live TWB bots and ACTS ON NOTHING yet — it's the shadow-run foundation (build it, run it
beside live on the same real events, compare, prove it, only then cut over).

Standing principles (enforced here from line one):
- TENANT-SCOPED: every row carries org_id; nothing is global.
- CHANNEL-AGNOSTIC: this core holds ZERO Telegram/web/app code — it exposes commands + emits events;
  channels are adapters elsewhere.
- ENTITY + EVENT: a shift is a first-class entity with a stable id; the date is a derived LABEL only;
  every change is an append-only event.
- INTERVAL-ONLY TIME: all logic reasons on absolute start_dt/end_dt instants — never a calendar-date
  comparison (the cure for the overnight bug-class).
- ATOMIC-CLAIM-AT-THE-WRITE: caps + single-application enforced at the DB write (UNIQUE-as-claim /
  conditional UPDATE), never trusted from a caller (the cure for the over-book bug-class).

(Working package name 'core' — renameable when the product is named.)
"""
