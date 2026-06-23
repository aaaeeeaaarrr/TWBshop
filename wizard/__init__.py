"""wizard — the config viewer/editor web adapter (a thin CLIENT; the brain stays server-side).

Stage 1 = READ-ONLY viewer of a tenant's effective config, every knob badged LIVE / SHADOW / PLANNED so
the owner sees what actually drives the shop vs what's only proving in the shadow vs what's not wired yet.
Security (CLAUDE.md ▶▶ PRODUCT SECURITY & IP): the engine/rules live here on the server; this serves
rendered views only, binds to localhost (reach via SSH tunnel), no secrets in any page. Editing + auth +
multi-tenant come in later stages.
"""
