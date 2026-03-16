"""AstrBot plugin entry for the OLV desktop-pet platform adapter."""

from __future__ import annotations

from astrbot.api.star import Context, Star


class MyPlugin(Star):
    """Minimal plugin entry that imports and registers the platform adapter."""

    def __init__(self, context: Context):
        super().__init__(context)
        from .platform_adapter import OLVPetPlatformAdapter  # noqa: F401
