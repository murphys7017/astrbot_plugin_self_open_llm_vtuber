from __future__ import annotations

from typing import Any, Awaitable, Callable
from uuid import uuid4


SUPPORTED_COMPAT_MESSAGE_TYPES = {
    "fetch-backgrounds",
    "fetch-configs",
    "fetch-history-list",
    "create-new-history",
    "fetch-and-set-history",
    "delete-history",
    "switch-config",
    "request-init-config",
    "heartbeat",
    "audio-play-start",
}


class FrontendCompatHandler:
    def __init__(
        self,
        *,
        background_files_getter: Callable[[], list[str]],
    ) -> None:
        self._background_files_getter = background_files_getter
        self._history_uid = str(uuid4())

    @staticmethod
    def can_handle(msg_type: str | None) -> bool:
        return msg_type in SUPPORTED_COMPAT_MESSAGE_TYPES

    async def handle(
        self,
        message: dict[str, Any],
        *,
        send_json: Callable[[dict[str, Any]], Awaitable[bool]],
        refresh_and_send_model: Callable[..., Awaitable[None]],
    ) -> None:
        msg_type = message.get("type")

        if msg_type == "fetch-backgrounds":
            await send_json(
                {"type": "background-files", "files": self._background_files_getter()}
            )
        elif msg_type == "fetch-configs":
            await send_json({"type": "config-files", "configs": []})
        elif msg_type == "fetch-history-list":
            await send_json({"type": "history-list", "histories": []})
        elif msg_type == "create-new-history":
            self._history_uid = str(uuid4())
            await send_json(
                {"type": "new-history-created", "history_uid": self._history_uid}
            )
        elif msg_type == "fetch-and-set-history":
            await send_json({"type": "history-data", "messages": []})
        elif msg_type == "delete-history":
            await send_json(
                {
                    "type": "history-deleted",
                    "success": True,
                    "history_uid": message.get("history_uid"),
                }
            )
        elif msg_type == "switch-config":
            await send_json(
                {
                    "type": "config-switched",
                    "message": "Config switch is not enabled in this adapter.",
                }
            )
        elif msg_type == "request-init-config":
            await refresh_and_send_model(force=True)
        elif msg_type == "heartbeat":
            await send_json({"type": "heartbeat-ack"})
