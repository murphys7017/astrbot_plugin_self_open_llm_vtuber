"""AstrBot platform adapter for the OLV desktop-pet frontend."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

from astrbot import logger
from astrbot.api.message_components import Image, Plain, Record
from astrbot.api.platform import (
    AstrBotMessage,
    MessageMember,
    MessageType,
    Platform,
    PlatformMetadata,
    register_platform_adapter,
)
from astrbot.core.platform.astr_message_event import MessageSesion


from .adapter.expression_mapper import RuleBasedExpressionMapper
from .adapter.payload_builder import (
    build_audio_payload,
    build_backend_synth_complete,
    build_control,
    build_error,
    build_force_new_message,
    build_full_text,
    build_set_model_and_conf,
)
from .adapter.protocol import ProtocolError, normalize_inbound_message
from .adapter.session_state import SessionState
from .platform_event import OLVPetPlatformEvent


@register_platform_adapter(
    "olv_pet_adapter",
    "OLV Pet Adapter",
    default_config_tmpl={
        "host": "127.0.0.1",
        "port": 12396,
        "conf_name": "AstrBot Desktop",
        "conf_uid": "astrbot-desktop",
        "speaker_name": "AstrBot",
        "model_info_json": "{}",
        "auto_start_mic": True,
    },
)
class OLVPetPlatformAdapter(Platform):
    """Platform adapter that accepts OLV websocket messages and emits AstrBot events."""

    def __init__(self, platform_config: Any, platform_settings: dict[str, Any], event_queue: Any):
        super().__init__(event_queue)
        self.config = platform_config
        self.settings = platform_settings or {}

        self.host = _config_get(self.config, "host", "127.0.0.1")
        self.port = int(_config_get(self.config, "port", 12396))
        self.client_uid = "desktop-client"
        self.conf_name = _config_get(self.config, "conf_name", "AstrBot Desktop")
        self.conf_uid = _config_get(self.config, "conf_uid", "astrbot-desktop")
        self.speaker_name = _config_get(self.config, "speaker_name", "AstrBot")
        self.auto_start_mic = bool(_config_get(self.config, "auto_start_mic", True))
        self.model_info = _parse_model_info(
            _config_get(self.config, "model_info_json", "{}")
        )

        self.session_state = SessionState(client_uid=self.client_uid)
        self.expression_mapper = RuleBasedExpressionMapper()

        self._ws_server = None
        self._ws_client = None
        self._turn_lock = asyncio.Lock()
        self._history_uid = str(uuid4())

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata("olv_pet_adapter", "OLV Pet Adapter")

    async def run(self):
        import websockets  # type: ignore

        self._ws_server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port,
            max_size=16 * 1024 * 1024,
        )
        logger.info(f"OLV Pet Adapter websocket listening on ws://{self.host}:{self.port}")
        await self._ws_server.wait_closed()

    async def send_by_session(self, session: MessageSesion, message_chain):
        await super().send_by_session(session, message_chain)

    def convert_message(self, data: dict[str, Any]) -> AstrBotMessage:
        inbound = normalize_inbound_message(data)

        abm = AstrBotMessage()
        abm.type = MessageType.FRIEND_MESSAGE
        abm.self_id = "olv_pet_adapter"
        abm.session_id = self.client_uid
        abm.message_id = str(uuid4())
        abm.message_str = inbound.payload.text
        abm.raw_message = data
        abm.sender = MessageMember(user_id=self.client_uid, nickname="DesktopUser")
        abm.message = [Plain(text=inbound.payload.text)]

        for image_payload in inbound.payload.images:
            image_component = self._convert_image_component(image_payload)
            if image_component is not None:
                abm.message.append(image_component)

        return abm

    async def handle_msg(self, message: dict[str, Any]):
        msg_type = message.get("type")

        if msg_type in {
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
        }:
            await self._handle_frontend_compat(message)
            return

        if msg_type == "frontend-playback-complete":
            await self._finalize_turn()
            return

        try:
            message_obj = self.convert_message(message)
        except ProtocolError as exc:
            logger.debug(f"Ignoring unsupported OLV message: {exc}")
            return

        async with self._turn_lock:
            if self.session_state.waiting_for_playback_complete:
                await self._finalize_turn()

            self.session_state.begin_turn(message_obj.message_str)
            await self._send_json(build_control("conversation-chain-start"))

            event = OLVPetPlatformEvent(
                message_obj.message_str,
                message_obj,
                self.meta(),
                message_obj.session_id,
                self,
            )
            self.commit_event(event)

    async def _handle_client(self, websocket):
        if self._ws_client is not None:
            await websocket.send(json.dumps(build_error("Only one client is supported.")))
            await websocket.close()
            return

        self._ws_client = websocket
        logger.info("Desktop frontend connected to OLV Pet Adapter.")
        try:
            await self._send_initial_messages()
            async for raw_message in websocket:
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8", errors="ignore")
                try:
                    parsed = json.loads(raw_message)
                except json.JSONDecodeError:
                    await self._send_json(build_error("Invalid JSON payload"))
                    continue
                await self.handle_msg(parsed)
        finally:
            self._ws_client = None
            self.session_state.reset_to_idle()
            logger.info("Desktop frontend disconnected from OLV Pet Adapter.")

    async def emit_message_chain(
        self,
        message_chain,
        unified_msg_origin: str | None = None,
    ) -> None:
        texts: list[str] = []
        picture_paths: list[str] = []
        record_paths: list[str] = []

        for component in _iter_message_chain(message_chain):
            if isinstance(component, Plain) and component.text.strip():
                texts.append(component.text.strip())
            elif isinstance(component, Image):
                image_path = getattr(component, "file", None)
                if isinstance(image_path, str) and image_path:
                    picture_paths.append(image_path)
            elif isinstance(component, Record):
                record_path = getattr(component, "file", None)
                if isinstance(record_path, str) and record_path:
                    record_paths.append(record_path)

        reply_text = "\n".join(texts).strip()
        if reply_text:
            await self._send_json(build_full_text(reply_text))

        actions = self.expression_mapper.decide(reply_text).actions if reply_text else None
        if actions and picture_paths:
            actions = {**actions, "pictures": picture_paths}
        elif picture_paths:
            actions = {"pictures": picture_paths}

        if record_paths:
            record_path = record_paths[0]
            await self._send_json(
                build_audio_payload(
                    audio_path=record_path,
                    text=reply_text,
                    speaker_name=self.speaker_name,
                    avatar="",
                    action_mapping=actions,
                )
            )
            await self._send_json(build_backend_synth_complete())
            self.session_state.mark_playing()
            return

        if reply_text:
            self.session_state.reset_to_idle()
            await self._send_json(build_backend_synth_complete())
            await self._send_json(build_force_new_message())
            await self._send_json(build_control("conversation-chain-end"))

    async def _send_initial_messages(self) -> None:
        await self._send_json(build_full_text("Connection established"))
        await self._send_json(
            build_set_model_and_conf(
                model_info=self.model_info,
                conf_name=self.conf_name,
                conf_uid=self.conf_uid,
                client_uid=self.client_uid,
            )
        )
        await self._send_json({"type": "group-update", "members": [], "is_owner": False})
        if self.auto_start_mic:
            await self._send_json(build_control("start-mic"))

    async def _handle_frontend_compat(self, message: dict[str, Any]) -> None:
        msg_type = message.get("type")

        if msg_type == "fetch-backgrounds":
            await self._send_json({"type": "background-files", "files": []})
        elif msg_type == "fetch-configs":
            await self._send_json({"type": "config-files", "configs": []})
        elif msg_type == "fetch-history-list":
            await self._send_json({"type": "history-list", "histories": []})
        elif msg_type == "create-new-history":
            self._history_uid = str(uuid4())
            await self._send_json(
                {"type": "new-history-created", "history_uid": self._history_uid}
            )
        elif msg_type == "fetch-and-set-history":
            await self._send_json({"type": "history-data", "messages": []})
        elif msg_type == "delete-history":
            await self._send_json(
                {
                    "type": "history-deleted",
                    "success": True,
                    "history_uid": message.get("history_uid"),
                }
            )
        elif msg_type == "switch-config":
            await self._send_json(
                {
                    "type": "config-switched",
                    "message": "Config switch is not enabled in this adapter.",
                }
            )
        elif msg_type == "request-init-config":
            await self._send_json(
                build_set_model_and_conf(
                    model_info=self.model_info,
                    conf_name=self.conf_name,
                    conf_uid=self.conf_uid,
                    client_uid=self.client_uid,
                )
            )
        elif msg_type == "heartbeat":
            await self._send_json({"type": "heartbeat-ack"})

    async def _finalize_turn(self) -> None:
        if not self.session_state.waiting_for_playback_complete:
            return
        await self._send_json(build_force_new_message())
        await self._send_json(build_control("conversation-chain-end"))
        self.session_state.mark_playback_complete()

    async def _send_json(self, payload: dict[str, Any]) -> None:
        if self._ws_client is None:
            return
        await self._ws_client.send(json.dumps(payload, ensure_ascii=False))

    @staticmethod
    def _convert_image_component(image_payload: Any):
        if isinstance(image_payload, str) and image_payload:
            return Image.fromURL(url=image_payload)

        if not isinstance(image_payload, dict):
            return None

        data = image_payload.get("data")
        mime_type = image_payload.get("mime_type", "image/png")
        if isinstance(data, str) and data:
            if data.startswith("http://") or data.startswith("https://"):
                return Image.fromURL(url=data)
            if data.startswith("data:"):
                return Image(file=data)
            return Image(file=f"data:{mime_type};base64,{data}")
        return None


def _iter_message_chain(message_chain) -> list[Any]:
    if message_chain is None:
        return []
    if hasattr(message_chain, "chain") and isinstance(message_chain.chain, list):
        return message_chain.chain
    if isinstance(message_chain, list):
        return message_chain
    return [message_chain]


def _config_get(config: Any, key: str, default: Any) -> Any:
    if config is None:
        return default
    if hasattr(config, "get"):
        value = config.get(key, default)
        return default if value is None else value
    if hasattr(config, key):
        value = getattr(config, key)
        return default if value is None else value
    return default


def _parse_model_info(raw_model_info: Any) -> dict[str, Any]:
    if isinstance(raw_model_info, dict):
        return raw_model_info
    if isinstance(raw_model_info, str):
        try:
            return json.loads(raw_model_info)
        except json.JSONDecodeError:
            logger.warning("Invalid `model_info_json`, falling back to empty object.")
    return {}
