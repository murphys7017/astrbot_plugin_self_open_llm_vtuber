from __future__ import annotations
"""AstrBot platform adapter for the OLV desktop-pet frontend."""
import asyncio
import time
from pathlib import Path

from astrbot.api.platform import Platform, AstrBotMessage, MessageMember, PlatformMetadata, MessageType
from astrbot.api.message_components import Plain
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.api.platform import register_platform_adapter
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import (
    get_astrbot_plugin_data_path,
)
import json
import traceback
from typing import Any
from uuid import uuid4

from .adapter.audio_runtime import create_vad_engine
from .adapter.chat_buffer import ChatBuffer
from .adapter.frontend_compat import FrontendCompatHandler
from .adapter.media_service import MediaService
from .adapter.model_info import build_static_routes, list_background_files
from .adapter.payload_builder import build_control, build_error, build_full_text
from .adapter.protocol import normalize_inbound_message
from .adapter.runtime_state import RuntimeState
from .adapter.session_state import SessionState
from .adapter.turn_coordinator import TurnCoordinator
from .platform_event import OLVPetPlatformEvent
from .static_resources import StaticResourceServer

PLUGIN_DIR = Path(__file__).resolve().parent
LIVE2DS_DIR = PLUGIN_DIR / "live2ds"
OLV_DIR = PLUGIN_DIR / "olv"
PLUGIN_DATA_DIR = Path(get_astrbot_plugin_data_path()) / PLUGIN_DIR.name
RUNTIME_CACHE_DIR = PLUGIN_DATA_DIR / "cache"
AUDIO_CACHE_DIR = RUNTIME_CACHE_DIR / "audio"
IMAGE_CACHE_DIR = RUNTIME_CACHE_DIR / "images"


@register_platform_adapter(
    "olv_pet_adapter",
    "OLV Pet Adapter",
    default_config_tmpl={
        "host": "127.0.0.1",
        "port": 12396,
        "http_port": 12397,
        "conf_name": "AstrBot Desktop",
        "conf_uid": "astrbot-desktop",
        "speaker_name": "AstrBot",
        "model_info_json": "{}",
        "auto_start_mic": True,
    },
)
class OLVPetPlatformAdapter(Platform):
    """Platform adapter that accepts OLV websocket messages and emits AstrBot events."""

    def __init__(self, platform_config: dict, platform_settings: dict, event_queue: asyncio.Queue) -> None:
        super().__init__(platform_config, event_queue)
        logger.info("OLVPetPlatformAdapter super().__init__ completed")
        self.config = platform_config
        self.settings = platform_settings or {}

        self.host = _config_get(self.config, "host", "127.0.0.1")
        self.port = int(_config_get(self.config, "port", 12396))
        self.http_port = int(_config_get(self.config, "http_port", 12397))
        self.client_uid = "desktop-client"
        self.conf_name = _config_get(self.config, "conf_name", "AstrBot Desktop")
        self.conf_uid = _config_get(self.config, "conf_uid", "astrbot-desktop")
        self.speaker_name = _config_get(self.config, "speaker_name", "AstrBot")
        self.auto_start_mic = bool(_config_get(self.config, "auto_start_mic", True))
        self.runtime_state = RuntimeState(
            platform_config=self.config,
            host=self.host,
            http_port=self.http_port,
            client_uid=self.client_uid,
            live2ds_dir=LIVE2DS_DIR,
        )

        self.session_state = SessionState(client_uid=self.client_uid)

        self._ws_server = None
        self._ws_client = None
        self._static_server = StaticResourceServer(
            host=self.host,
            port=self.http_port,
            routes=build_static_routes(
                live2ds_dir=LIVE2DS_DIR,
                olv_dir=OLV_DIR,
                runtime_cache_dir=RUNTIME_CACHE_DIR,
            ),
        )
        self.media_service = MediaService(
            host=self.host,
            http_port=self.http_port,
            live2ds_dir=LIVE2DS_DIR,
            olv_dir=OLV_DIR,
            audio_cache_dir=AUDIO_CACHE_DIR,
            image_cache_dir=IMAGE_CACHE_DIR,
        )
        self.frontend_compat_handler = FrontendCompatHandler(
            background_files_getter=lambda: list_background_files(OLV_DIR)
        )
        self._vad_engine = None
        self._last_accepted_image_at_monotonic: float | None = None
        self.chat_buffer = ChatBuffer(
            maxlen=int(_plugin_config_get(self.runtime_state.plugin_config, "chat_buffer_size", 10))
        )
        self.turn_coordinator = TurnCoordinator(
            session_state=self.session_state,
            runtime_state=self.runtime_state,
            media_service=self.media_service,
            chat_buffer=self.chat_buffer,
            speaker_name=self.speaker_name,
            convert_message=self.convert_message,
            build_message_object=self._build_message_object,
            handle_frontend_compat=self._handle_frontend_compat,
            refresh_runtime_settings=self._refresh_runtime_settings,
            send_current_model_and_conf=self._send_current_model_and_conf,
            send_json=self._send_json,
            build_platform_event=self._build_platform_event,
            commit_event=self.commit_event,
            ensure_vad_engine=self._ensure_vad_engine,
        )

        logger.info(
            "OLVPetPlatformAdapter initialized "
            f"(host={self.host}, port={self.port}, http_port={self.http_port}, "
            f"conf_name={self.conf_name}, conf_uid={self.conf_uid})"
        )
        self._refresh_runtime_settings()

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="olv_pet_adapter",
            description="OLV Pet Adapter",
            id="olv_pet_adapter",
        )

    @property
    def vad_model(self) -> str:
        return self.runtime_state.vad_model

    @property
    def vad_config(self) -> dict[str, Any]:
        return self.runtime_state.vad_config

    @property
    def model_info(self) -> dict[str, Any]:
        return self.runtime_state.model_info

    @property
    def image_cooldown_seconds(self) -> int:
        return self.runtime_state.image_cooldown_seconds

    @property
    def _default_persona(self) -> dict[str, Any] | None:
        return self.runtime_state.default_persona

    @property
    def _selected_stt_provider(self):
        return self.runtime_state.selected_stt_provider

    @property
    def _selected_expression_provider(self):
        return self.runtime_state.selected_expression_provider

    async def run(self):
        logger.info("OLV Pet Adapter entering run()")
        try:
            import websockets  # type: ignore

            logger.info("OLV Pet Adapter imported `websockets` successfully")
            await self._refresh_runtime_settings_async(
                reload_persona=True,
                reload_providers=True,
            )
            await asyncio.to_thread(self._static_server.start)
            logger.info(
                f"OLV Pet Adapter starting websocket server on ws://{self.host}:{self.port}"
            )

            self._ws_server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port,
                max_size=16 * 1024 * 1024,
            )
            logger.info(f"OLV Pet Adapter websocket listening on ws://{self.host}:{self.port}")
            await self._ws_server.wait_closed()
        except asyncio.CancelledError:
            logger.info("OLV Pet Adapter run() cancelled, shutting down websocket server")
            await self.terminate()
            raise
        except Exception as exc:
            logger.error(f"OLV Pet Adapter failed during run(): {exc}")
            logger.error(traceback.format_exc())
            raise

    async def send_by_session(self, session: MessageSesion, message_chain):
        await super().send_by_session(session, message_chain)

    def convert_message(self, data: dict[str, Any]) -> AstrBotMessage:
        inbound = normalize_inbound_message(data)
        return self._build_message_object(
            text=inbound.payload.text,
            raw_message=data,
            images=inbound.payload.images,
        )

    def _build_message_object(
        self,
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

    def _build_platform_event(self, message_obj: AstrBotMessage) -> OLVPetPlatformEvent:
        return OLVPetPlatformEvent(
            message_obj.message_str,
            message_obj,
            self.meta(),
            message_obj.session_id,
            self,
        )

    async def handle_msg(self, message: dict[str, Any]):
        await self.turn_coordinator.handle_msg(message)

    def _ensure_vad_engine(self):
        if self._vad_engine is not None:
            return self._vad_engine
        self._vad_engine = create_vad_engine(
            olv_dir=OLV_DIR,
            engine_type=self.vad_model,
            kwargs=self.vad_config,
        )
        return self._vad_engine

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
            await self.media_service.clear_audio_buffer()
            logger.info("Desktop frontend disconnected from OLV Pet Adapter.")

    async def emit_message_chain(
        self,
        message_chain,
        unified_msg_origin: str | None = None,
    ) -> None:
        await self.turn_coordinator.emit_message_chain(
            message_chain=message_chain,
            unified_msg_origin=unified_msg_origin,
        )

    async def _send_initial_messages(self) -> None:
        await self._refresh_runtime_settings_async(
            reload_persona=True,
            reload_providers=True,
        )
        await self._send_json(build_full_text("Connection established"))
        await self._send_current_model_and_conf(force=True)
        await self._send_json({"type": "group-update", "members": [], "is_owner": False})
        if self.auto_start_mic:
            await self._send_json(build_control("start-mic"))

    def _refresh_runtime_settings(self) -> None:
        vad_settings_changed = self.runtime_state.refresh()
        if self._vad_engine is not None and vad_settings_changed:
            self._vad_engine = None

    async def _refresh_runtime_settings_async(
        self,
        *,
        reload_persona: bool = False,
        reload_providers: bool = False,
    ) -> None:
        vad_settings_changed = await self.runtime_state.refresh_async(
            reload_persona=reload_persona,
            reload_providers=reload_providers,
        )
        if self._vad_engine is not None and vad_settings_changed:
            self._vad_engine = None

    async def _send_current_model_and_conf(self, *, force: bool = False) -> None:
        payload = self.runtime_state.build_current_model_payload(
            conf_name=self.conf_name,
            conf_uid=self.conf_uid,
            client_uid=self.client_uid,
        )
        if not self.runtime_state.should_send_model_payload(payload, force=force):
            return
        await self._send_json(payload)
        self.runtime_state.mark_model_payload_sent(payload)

    async def _refresh_and_send_current_model_and_conf(self, *, force: bool = False) -> None:
        self._refresh_runtime_settings()
        await self._send_current_model_and_conf(force=force)

    def _apply_image_cooldown(self, images: list[Any]) -> tuple[list[Any], int]:
        if not images:
            return [], 0

        if self.image_cooldown_seconds <= 0:
            self._last_accepted_image_at_monotonic = time.monotonic()
            return images, 0

        now = time.monotonic()
        last_accepted = self._last_accepted_image_at_monotonic
        if last_accepted is None or (now - last_accepted) >= self.image_cooldown_seconds:
            self._last_accepted_image_at_monotonic = now
            return images, 0

        logger.info(
            "Dropped %s image(s) due to cooldown window (%ss remaining approximately).",
            len(images),
            max(int(self.image_cooldown_seconds - (now - last_accepted)), 0),
        )
        return [], len(images)

    async def _handle_frontend_compat(self, message: dict[str, Any]) -> None:
        await self.frontend_compat_handler.handle(
            message,
            send_json=self._send_json,
            refresh_and_send_model=self._refresh_and_send_current_model_and_conf,
        )

    async def terminate(self) -> None:
        logger.info("OLV Pet Adapter terminate() called")

        if self._ws_client is not None:
            try:
                await self._ws_client.close()
            except Exception as exc:
                logger.warning(f"Failed to close desktop websocket client cleanly: {exc}")
            finally:
                self._ws_client = None

        if self._ws_server is not None:
            try:
                self._ws_server.close()
                await self._ws_server.wait_closed()
            except Exception as exc:
                logger.warning(f"Failed to close websocket server cleanly: {exc}")
            finally:
                self._ws_server = None

        if self._static_server is not None:
            try:
                await asyncio.to_thread(self._static_server.stop)
            except Exception as exc:
                logger.warning(f"Failed to close static resource server cleanly: {exc}")

    async def _finalize_turn(self) -> None:
        await self.turn_coordinator.finalize_turn()

    async def _send_json(self, payload: dict[str, Any]) -> bool:
        client = self._ws_client
        if client is None:
            return False
        try:
            await client.send(json.dumps(payload, ensure_ascii=False))
            return True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self._ws_client is client:
                self._ws_client = None
            logger.warning(f"Failed to send websocket payload `{payload.get('type', '<unknown>')}`: {exc}")
            try:
                await client.close()
            except Exception:
                pass
            return False

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


def _plugin_config_get(config: Any, key: str, default: Any) -> Any:
    if config is None:
        return default
    if hasattr(config, "get"):
        value = config.get(key, default)
        return default if value is None else value
    return default
