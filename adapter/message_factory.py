from __future__ import annotations

import time
from typing import Any, Callable
from uuid import uuid4

from astrbot.api.message_components import Plain
from astrbot.api.platform import AstrBotMessage, MessageMember, MessageType
from astrbot.api import logger

from .protocol import normalize_inbound_message


class MessageFactory:
    def __init__(
        self,
        *,
        client_uid: str,
        media_service,
        image_cooldown_seconds_getter: Callable[[], int],
    ) -> None:
        self.client_uid = client_uid
        self.media_service = media_service
        self._image_cooldown_seconds_getter = image_cooldown_seconds_getter
        self._last_accepted_image_at_monotonic: float | None = None

    def convert_message(self, data: dict[str, Any]) -> AstrBotMessage:
        inbound = normalize_inbound_message(data)
        return self.build_message_object(
            text=inbound.payload.text,
            raw_message=data,
            images=inbound.payload.images,
        )

    def build_message_object(
        self,
        *,
        text: str,
        raw_message: dict[str, Any],
        images: list[Any] | None = None,
    ) -> AstrBotMessage:
        images = images or []
        accepted_images, dropped_image_count = self._apply_image_cooldown(images)

        abm = AstrBotMessage()
        abm.type = MessageType.FRIEND_MESSAGE
        abm.self_id = "olv_pet_adapter"
        abm.session_id = self.client_uid
        abm.message_id = str(uuid4())
        abm.message_str = text
        abm.sender = MessageMember(user_id=self.client_uid, nickname="DesktopUser")
        abm.message = [Plain(text=text)]
        normalized_raw_message = dict(raw_message)
        resolved_image_inputs: list[dict[str, str]] = []

        for image_payload in accepted_images:
            image_component = self.media_service.convert_image_component(image_payload)
            if image_component is not None:
                abm.message.append(image_component)
                image_ref = (
                    (getattr(image_component, "file", "") or "").strip()
                    or (getattr(image_component, "url", "") or "").strip()
                )
                if image_ref:
                    resolved_image_inputs.append(
                        {"type": "input_image", "image_url": image_ref}
                    )

        if resolved_image_inputs:
            normalized_raw_message["resolved_images"] = resolved_image_inputs
        if dropped_image_count > 0:
            normalized_raw_message["dropped_image_count"] = dropped_image_count
        abm.raw_message = normalized_raw_message

        return abm

    def _apply_image_cooldown(self, images: list[Any]) -> tuple[list[Any], int]:
        if not images:
            return [], 0

        image_cooldown_seconds = self._image_cooldown_seconds_getter()
        if image_cooldown_seconds <= 0:
            self._last_accepted_image_at_monotonic = time.monotonic()
            return images, 0

        now = time.monotonic()
        last_accepted = self._last_accepted_image_at_monotonic
        if last_accepted is None or (now - last_accepted) >= image_cooldown_seconds:
            self._last_accepted_image_at_monotonic = now
            return images, 0

        logger.info(
            "Dropped %s image(s) due to cooldown window (%ss remaining approximately).",
            len(images),
            max(int(image_cooldown_seconds - (now - last_accepted)), 0),
        )
        return [], len(images)
