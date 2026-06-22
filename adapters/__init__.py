"""adapters — the platform's CHANNELS. Each adapter translates a channel's native input into a neutral
core.channel command and renders the neutral result. The brain (core/) holds no channel code; channels
live here (telegram, web, app, …) and are enabled per-tenant via config. (docs/PLATFORM_VISION.md #1.)
"""
