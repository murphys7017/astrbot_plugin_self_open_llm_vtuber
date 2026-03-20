from __future__ import annotations
"""AstrBot platform adapter for the desktop VTuber frontend."""
import asyncio
from pathlib import Path

from astrbot.api.platform import Platform, AstrBotMessage, PlatformMetadata
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.api.platform import register_platform_adapter
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import (
    get_astrbot_plugin_data_path,
)
import traceback
from typing import Any
from uuid import uuid4

from .adapter.audio_runtime import create_vad_engine
from .adapter.chat_buffer import ChatBuffer
from .adapter.frontend_compat import FrontendCompatHandler
from .adapter.media_service import MediaService
from .adapter.message_factory import MessageFactory
from .adapter.model_info import build_static_routes, list_background_files
from .adapter.runtime_state import RuntimeState
from .adapter.session_state import SessionState
from .adapter.transport_ws import WebSocketTransport
from .adapter.turn_coordinator import TurnCoordinator
from .platform_event import OLVPetPlatformEvent
from .static_resources import StaticResourceServer

PLUGIN_DIR = Path(__file__).resolve().parent
LIVE2DS_DIR = PLUGIN_DIR / "live2ds"
FRONTEND_ASSETS_DIR = PLUGIN_DIR / "olv"
PLUGIN_DATA_DIR = Path(get_astrbot_plugin_data_path()) / PLUGIN_DIR.name
RUNTIME_CACHE_DIR = PLUGIN_DATA_DIR / "cache"
AUDIO_CACHE_DIR = RUNTIME_CACHE_DIR / "audio"
IMAGE_CACHE_DIR = RUNTIME_CACHE_DIR / "images"


@register_platform_adapter(
    "olv_pet_adapter",
    "Desktop VTuber Adapter",
    default_config_tmpl={
        "host": "127.0.0.1",
        "port": 12396,
        "http_port": 12397,
        "conf_name": "AstrBot Desktop",
        "conf_uid": "astrbot-desktop",
        "speaker_name": "AstrBot",
        "model_info_json": "{}",
        "auto_start_mic": True,
        "vad_model": "silero_vad",
    },
)
class OLVPetPlatformAdapter(Platform):
    """Platform adapter that accepts desktop VTuber websocket messages and emits AstrBot events."""

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

        self._static_server = StaticResourceServer(
            host=self.host,
            port=self.http_port,
            routes=build_static_routes(
                live2ds_dir=LIVE2DS_DIR,
                olv_dir=FRONTEND_ASSETS_DIR,
                runtime_cache_dir=RUNTIME_CACHE_DIR,
            ),
        )
        self.media_service = MediaService(
            host=self.host,
            http_port=self.http_port,
            live2ds_dir=LIVE2DS_DIR,
            olv_dir=FRONTEND_ASSETS_DIR,
            audio_cache_dir=AUDIO_CACHE_DIR,
            image_cache_dir=IMAGE_CACHE_DIR,
        )
        self.message_factory = MessageFactory(
            client_uid=self.client_uid,
            media_service=self.media_service,
            image_cooldown_seconds_getter=lambda: self.runtime_state.image_cooldown_seconds,
        )
        self.frontend_compat_handler = FrontendCompatHandler(
            background_files_getter=lambda: list_background_files(FRONTEND_ASSETS_DIR)
        )
        self.transport = WebSocketTransport(
            host=self.host,
            port=self.port,
            static_server=self._static_server,
            auto_start_mic=self.auto_start_mic,
            handle_message=self.handle_msg,
            refresh_runtime_settings_async=self._refresh_runtime_settings_async,
            send_current_model_and_conf=self._send_current_model_and_conf,
            on_disconnect=self._handle_transport_disconnect,
        )
        self._vad_engine = None
        self.chat_buffer = ChatBuffer(
            maxlen=int(_plugin_config_get(self.runtime_state.plugin_config, "chat_buffer_size", 10))
        )
        self.turn_coordinator = TurnCoordinator(
            session_state=self.session_state,
            runtime_state=self.runtime_state,
            media_service=self.media_service,
            chat_buffer=self.chat_buffer,
            speaker_name=self.speaker_name,
            convert_message=self.message_factory.convert_message,
            build_message_object=self.message_factory.build_message_object,
            handle_frontend_compat=self._handle_frontend_compat,
            refresh_runtime_settings=self._refresh_runtime_settings,
            send_current_model_and_conf=self._send_current_model_and_conf,
            send_json=self.transport.send_json,
            build_platform_event=self._build_platform_event,
            commit_event=self.commit_event,
            ensure_vad_engine=self._ensure_vad_engine,
        )

        logger.info(
            "Desktop VTuber Adapter initialized "
            f"(host={self.host}, port={self.port}, http_port={self.http_port}, "
            f"conf_name={self.conf_name}, conf_uid={self.conf_uid})"
        )
        self._refresh_runtime_settings()

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="olv_pet_adapter",
            description="Desktop VTuber Adapter",
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
        try:
            await self.transport.start()
        except asyncio.CancelledError:
            await self.terminate()
            raise
        except Exception as exc:
            logger.error(f"Desktop VTuber Adapter failed during run(): {exc}")
            logger.error(traceback.format_exc())
            raise

    async def send_by_session(self, session: MessageSesion, message_chain):
        await super().send_by_session(session, message_chain)

    def convert_message(self, data: dict[str, Any]) -> AstrBotMessage:
        return self.message_factory.convert_message(data)

    def _build_message_object(
        self,
        text: str,
        raw_message: dict[str, Any],
        images: list[Any] | None = None,
    ) -> AstrBotMessage:
        return self.message_factory.build_message_object(
            text=text,
            raw_message=raw_message,
            images=images,
        )

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
            olv_dir=FRONTEND_ASSETS_DIR,
            engine_type=self.vad_model,
            kwargs=self.vad_config,
        )
        return self._vad_engine

    async def emit_message_chain(
        self,
        message_chain,
        unified_msg_origin: str | None = None,
        inline_base_expression: str | None = None,
    ) -> None:
        await self.turn_coordinator.emit_message_chain(
            message_chain=message_chain,
            unified_msg_origin=unified_msg_origin,
            inline_base_expression=inline_base_expression,
        )

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

    async def _handle_frontend_compat(self, message: dict[str, Any]) -> None:
        await self.frontend_compat_handler.handle(
            message,
            send_json=self._send_json,
            refresh_and_send_model=self._refresh_and_send_current_model_and_conf,
        )

    async def terminate(self) -> None:
        logger.info("Desktop VTuber Adapter terminate() called")
        await self.transport.stop()

    async def _send_json(self, payload: dict[str, Any]) -> bool:
        return await self.transport.send_json(payload)

    async def _handle_transport_disconnect(self) -> None:
        self.session_state.reset_to_idle()
        await self.media_service.clear_audio_buffer()

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
