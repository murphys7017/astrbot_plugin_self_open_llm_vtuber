"""AstrBot event wrapper for the desktop VTuber websocket frontend."""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from .adapter.inline_expression import (
    LIVE2D_BASE_EXPRESSION_EXTRA_KEY,
    LIVE2D_MOTION_ID_EXTRA_KEY,
)


class OLVPetPlatformEvent(AstrMessageEvent):
    """Message event that sends AstrBot replies back to the desktop VTuber frontend."""

    def __init__(self, message_str, message_obj, platform_meta, session_id, adapter):
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.adapter = adapter

    async def send(self, message):
        await self.adapter.emit_message_chain(
            message_chain=message,
            unified_msg_origin=self.unified_msg_origin,
            inline_base_expression=self.get_extra(LIVE2D_BASE_EXPRESSION_EXTRA_KEY),
            inline_motion_id=self.get_extra(LIVE2D_MOTION_ID_EXTRA_KEY),
        )
        await super().send(message)
