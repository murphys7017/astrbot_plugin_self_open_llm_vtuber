from __future__ import annotations
"""AstrBot platform adapter for the OLV desktop-pet frontend."""
import asyncio
import os
from pathlib import Path
import numpy as np

from astrbot.api.platform import Platform, AstrBotMessage, MessageMember, PlatformMetadata, MessageType
from astrbot.api.message_components import Plain, Image, Record # 消息链中的组件，可以根据需要导入
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.api.platform import register_platform_adapter
from astrbot.api.provider import Provider, STTProvider
from astrbot import logger
from astrbot.core.utils.astrbot_path import get_astrbot_temp_path




import json
import traceback
from typing import Any
from uuid import uuid4

from .adapter.base_expression_planner import (
    BaseExpressionPlanningError,
    build_fallback_base_expression_decision,
    plan_base_expression,
)
from .adapter.base_expression_fallback import RuleBasedExpressionMapper
from .adapter.audio_runtime import create_vad_engine
from .adapter.chat_buffer import ChatBuffer
from .adapter.payload_builder import (
    build_audio_payload,
    build_backend_synth_complete,
    build_control,
    build_error,
    build_force_new_message,
    build_full_text,
    build_set_model_and_conf,
)
from .adapter.plugin_runtime import get_plugin_config, get_plugin_context
from .adapter.protocol import ProtocolError, normalize_inbound_message
from .adapter.session_state import SessionState
from .platform_event import OLVPetPlatformEvent
from .static_resources import StaticResourceServer

PLUGIN_DIR = Path(__file__).resolve().parent
LIVE2DS_DIR = PLUGIN_DIR / "live2ds"
OLV_DIR = PLUGIN_DIR / "olv"


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
        self._plugin_config = get_plugin_config() or {}
        self.stt_provider_id = ""
        self.expression_provider_id = ""
        self.vad_model = "silero_vad"
        self.vad_config: dict[str, Any] = {}
        self.live2d_model_name = ""
        self.model_info: dict[str, Any] = {}

        self.session_state = SessionState(client_uid=self.client_uid)
        self.expression_mapper = RuleBasedExpressionMapper()

        self._ws_server = None
        self._ws_client = None
        self._static_server = StaticResourceServer(
            host=self.host,
            port=self.http_port,
            routes=_build_static_routes(),
        )
        self._turn_lock = asyncio.Lock()
        self._history_uid = str(uuid4())
        self._audio_buffer = np.array([], dtype=np.float32)
        self._audio_buffer_lock = asyncio.Lock()
        self._vad_engine = None
        self._plugin_context = get_plugin_context()
        self._default_persona: dict[str, Any] | None = None
        self._selected_stt_provider: STTProvider | None = None
        self._selected_expression_provider: Provider | None = None
        self._last_sent_model_signature: str | None = None
        self.chat_buffer = ChatBuffer(
            maxlen=int(_plugin_config_get(self._plugin_config, "chat_buffer_size", 10))
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

    async def run(self):
        logger.info("OLV Pet Adapter entering run()")
        try:
            import websockets  # type: ignore

            logger.info("OLV Pet Adapter imported `websockets` successfully")
            await self._refresh_runtime_settings_async(
                reload_persona=True,
                reload_providers=True,
            )
            self._static_server.start()
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

        abm = AstrBotMessage()
        abm.type = MessageType.FRIEND_MESSAGE
        abm.self_id = "olv_pet_adapter"
        abm.session_id = self.client_uid
        abm.message_id = str(uuid4())
        abm.message_str = text
        abm.raw_message = raw_message
        abm.sender = MessageMember(user_id=self.client_uid, nickname="DesktopUser")
        abm.message = [Plain(text=text)]

        for image_payload in images:
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

        if msg_type == "mic-audio-data":
            await self._handle_audio_data(message)
            return

        if msg_type == "raw-audio-data":
            await self._handle_raw_audio_data(message)
            return

        if msg_type == "mic-audio-end":
            await self._handle_audio_end(message)
            return

        try:
            message_obj = self.convert_message(message)
        except ProtocolError as exc:
            logger.debug(f"Ignoring unsupported OLV message: {exc}")
            return

        await self._commit_inbound_message(message_obj)

    async def _commit_inbound_message(self, message_obj: AstrBotMessage) -> None:
        async with self._turn_lock:
            self._refresh_runtime_settings()
            await self._send_current_model_and_conf()
            if self.session_state.waiting_for_playback_complete:
                await self._finalize_turn()

            self.session_state.begin_turn(message_obj.message_str)
            self.chat_buffer.add("user", message_obj.message_str)
            await self._send_json(build_control("conversation-chain-start"))

            event = OLVPetPlatformEvent(
                message_obj.message_str,
                message_obj,
                self.meta(),
                message_obj.session_id,
                self,
            )
            self.commit_event(event)

    async def _handle_audio_data(self, message: dict[str, Any]) -> None:
        audio_data = message.get("audio", [])
        if not isinstance(audio_data, list) or not audio_data:
            return

        chunk = np.array(audio_data, dtype=np.float32)
        async with self._audio_buffer_lock:
            self._audio_buffer = np.append(self._audio_buffer, chunk)

    async def _handle_raw_audio_data(self, message: dict[str, Any]) -> None:
        audio_data = message.get("audio", [])
        if not isinstance(audio_data, list) or not audio_data:
            return

        try:
            vad_engine = self._ensure_vad_engine()
        except Exception as exc:
            logger.error(f"Failed to initialize VAD engine: {exc}")
            await self._send_json(build_error(f"VAD unavailable: {exc}"))
            return

        for audio_bytes in vad_engine.detect_speech(audio_data):
            if audio_bytes == b"<|PAUSE|>":
                await self._send_json(build_control("interrupt"))
            elif audio_bytes == b"<|RESUME|>":
                continue
            elif len(audio_bytes) > 1024:
                chunk = (
                    np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                )
                async with self._audio_buffer_lock:
                    self._audio_buffer = np.append(self._audio_buffer, chunk)
                await self._send_json(build_control("mic-audio-end"))

    async def _handle_audio_end(self, message: dict[str, Any]) -> None:
        async with self._audio_buffer_lock:
            audio_buffer = self._audio_buffer.copy()
            self._audio_buffer = np.array([], dtype=np.float32)

        if audio_buffer.size == 0:
            logger.debug("Ignoring `mic-audio-end` with empty buffer.")
            return

        try:
            text = (await self._transcribe_audio(audio_buffer)).strip()
        except Exception as exc:
            logger.error(f"Audio transcription failed: {exc}")
            await self._send_json(build_error(f"Audio transcription failed: {exc}"))
            return

        if not text:
            await self._send_json(build_error("The LLM can't hear you."))
            return

        await self._send_json({"type": "user-input-transcription", "text": text})

        raw_message = dict(message)
        raw_message["transcription"] = text
        raw_message["audio_sample_count"] = int(audio_buffer.size)
        message_obj = self._build_message_object(text=text, raw_message=raw_message)
        await self._commit_inbound_message(message_obj)

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
            self._audio_buffer = np.array([], dtype=np.float32)
            logger.info("Desktop frontend disconnected from OLV Pet Adapter.")

    async def emit_message_chain(
        self,
        message_chain,
        unified_msg_origin: str | None = None,
    ) -> None:
        texts: list[str] = []
        picture_paths: list[str] = []
        record_paths: list[str] = []
        logger.debug(f"Emitting message chain: {message_chain}")
        for component in _iter_message_chain(message_chain):
            if isinstance(component, Plain) and component.text.strip():
                texts.append(component.text.strip())
            elif isinstance(component, Image):
                image_path = getattr(component, "file", None)
                if isinstance(image_path, str) and image_path:
                    picture_paths.append(image_path)
            elif isinstance(component, Record):
                # Extract text from Record if available
                record_text = getattr(component, "text", None)
                if record_text and isinstance(record_text, str) and record_text.strip():
                    texts.append(record_text.strip())
                # Also extract file path
                record_path = getattr(component, "file", None)
                if isinstance(record_path, str) and record_path:
                    record_paths.append(record_path)

        reply_text = "\n".join(texts).strip()
        if reply_text:
            self.chat_buffer.add("assistant", reply_text)
            await self._send_json(build_full_text(reply_text))

        # Build expression actions from reply text
        actions = {}
        if reply_text:
            try:
                expr_actions = await self._build_expression_actions(reply_text)
                if expr_actions:
                    actions.update(expr_actions)
            except Exception as exc:
                logger.warning(f"Failed to build expression actions: {exc}")
        
        # Add pictures if available
        if picture_paths:
            actions["pictures"] = picture_paths
        
        # Send actions only if non-empty
        actions_to_send = actions if actions else None

        if record_paths:
            record_path = record_paths[0]
            await self._send_json(
                build_audio_payload(
                    audio_path=record_path,
                    text=reply_text,
                    speaker_name=self.speaker_name,
                    avatar="",
                    action_mapping=actions_to_send,
                )
            )
            await self._send_json(build_backend_synth_complete())
            self.session_state.mark_playing()
            return

        if actions_to_send:
            await self._send_json(
                build_audio_payload(
                    audio_path="",
                    text=reply_text,
                    speaker_name=self.speaker_name,
                    avatar="",
                    action_mapping=actions_to_send,
                )
            )

        if reply_text:
            self.session_state.reset_to_idle()
            await self._send_json(build_backend_synth_complete())
            await self._send_json(build_force_new_message())
            await self._send_json(build_control("conversation-chain-end"))

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

    async def _load_default_persona(self) -> None:
        if self._plugin_context is None:
            logger.warning("Plugin context is unavailable, skip loading default persona.")
            return

        configured_persona_id = _plugin_config_get(self._plugin_config, "persona_id", "")
        try:
            persona = None
            if configured_persona_id:
                persona = next(
                    (
                        item
                        for item in self._plugin_context.persona_manager.personas_v3
                        if item["name"] == configured_persona_id
                    ),
                    None,
                )
                if persona is None:
                    logger.warning(
                        f"Configured persona `{configured_persona_id}` not found, fallback to default persona."
                    )

            if persona is None:
                persona = await self._plugin_context.persona_manager.get_default_persona_v3(
                    umo=self.client_uid
                )
        except Exception as exc:
            logger.warning(f"Failed to load default persona: {exc}")
            return

        self._default_persona = {
            "name": persona.get("name", "default"),
            "prompt": persona.get("prompt", ""),
            "begin_dialogs": persona.get("begin_dialogs", []),
            "custom_error_message": persona.get("custom_error_message"),
        }
        logger.info(f"Loaded default persona: {self._default_persona['name']}")

    def _refresh_runtime_settings(self) -> None:
        latest_plugin_config = get_plugin_config()
        if latest_plugin_config is not None:
            self._plugin_config = latest_plugin_config

        previous_vad_model = self.vad_model
        previous_vad_config = dict(self.vad_config)

        self.stt_provider_id = _plugin_config_get(self._plugin_config, "stt_provider_id", "")
        self.expression_provider_id = _plugin_config_get(
            self._plugin_config, "expression_provider_id", ""
        )
        self.vad_model = _plugin_config_get(
            self._plugin_config, "vad_model", "silero_vad"
        )
        self.vad_config = {
            "orig_sr": 16000,
            "target_sr": 16000,
            "prob_threshold": float(_plugin_config_get(self._plugin_config, "vad_prob_threshold", 0.4)),
            "db_threshold": int(_plugin_config_get(self._plugin_config, "vad_db_threshold", 60)),
            "required_hits": int(_plugin_config_get(self._plugin_config, "vad_required_hits", 3)),
            "required_misses": int(_plugin_config_get(self._plugin_config, "vad_required_misses", 24)),
            "smoothing_window": int(_plugin_config_get(self._plugin_config, "vad_smoothing_window", 5)),
        }
        self.live2d_model_name = _plugin_config_get(
            self._plugin_config, "live2d_model_name", ""
        )
        self.model_info = _parse_model_info(
            _config_get(self.config, "model_info_json", "{}"),
            host=self.host,
            http_port=self.http_port,
            selected_model_name=self.live2d_model_name,
        )

        if self._vad_engine is not None and (
            self.vad_model != previous_vad_model or self.vad_config != previous_vad_config
        ):
            self._vad_engine = None

        logger.info(
            "Refreshed plugin runtime settings "
            f"(live2d_model_name={self.live2d_model_name or '<default>'}, "
            f"model_url={self.model_info.get('url', '<missing>')})"
        )

    async def _refresh_runtime_settings_async(
        self,
        *,
        reload_persona: bool = False,
        reload_providers: bool = False,
    ) -> None:
        self._refresh_runtime_settings()

        if reload_persona:
            await self._load_default_persona()

        if reload_providers:
            self._selected_stt_provider = None
            self._selected_expression_provider = None
            self._load_selected_providers()

    async def _send_current_model_and_conf(self, *, force: bool = False) -> None:
        payload = build_set_model_and_conf(
            model_info=self.model_info,
            conf_name=self.conf_name,
            conf_uid=self.conf_uid,
            client_uid=self.client_uid,
        )
        signature = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        if not force and signature == self._last_sent_model_signature:
            return
        await self._send_json(payload)
        self._last_sent_model_signature = signature

    def _load_selected_providers(self) -> None:
        if self._plugin_context is None:
            logger.warning("Plugin context is unavailable, skip loading providers from plugin config.")
            return

        if self.stt_provider_id:
            provider = self._plugin_context.get_provider_by_id(self.stt_provider_id)
            if isinstance(provider, STTProvider):
                self._selected_stt_provider = provider
                logger.info(f"Loaded STT provider from plugin config: {self.stt_provider_id}")
            else:
                logger.warning(f"Configured STT provider `{self.stt_provider_id}` not found or not a STTProvider.")
        else:
            try:
                provider = self._plugin_context.get_using_stt_provider(umo=self.client_uid)
            except Exception as exc:
                logger.warning(f"Failed to get current STT provider: {exc}")
                provider = None
            if isinstance(provider, STTProvider):
                self._selected_stt_provider = provider
                logger.info(f"Using current STT provider: {provider.meta().id}")

        if self.expression_provider_id:
            provider = self._plugin_context.get_provider_by_id(self.expression_provider_id)
            if isinstance(provider, Provider):
                self._selected_expression_provider = provider
                logger.info(
                    f"Loaded expression planner provider from plugin config: {self.expression_provider_id}"
                )
            else:
                logger.warning(
                    f"Configured expression provider `{self.expression_provider_id}` not found or not a chat Provider."
                )

    async def _build_expression_actions(self, reply_text: str) -> dict[str, Any] | None:
        if not reply_text:
            return None

        emotion_map = self.model_info.get("emotionMap") or {}
        emotion_map_keys = [
            key for key in emotion_map.keys() if isinstance(key, str) and key
        ]
        decision = build_fallback_base_expression_decision(reply_text, emotion_map_keys)
        planner_error = None
        if self._selected_expression_provider is not None:
            try:
                decision = await plan_base_expression(
                    self._selected_expression_provider,
                    persona=self._default_persona,
                    chatbuffer=self.chat_buffer.to_list(),
                    user_input=self.session_state.last_user_text,
                    reply_text=reply_text,
                    emotion_map_keys=emotion_map_keys,
                )
            except BaseExpressionPlanningError as exc:
                planner_error = str(exc)
                logger.warning(f"Base expression planner validation failed, fallback to local mapping: {exc}")
            except Exception as exc:
                planner_error = str(exc)
                logger.warning(f"Base expression planner failed, fallback to local mapping: {exc}")

        resolved_expression = emotion_map.get(
            decision.base_expression,
            next(iter(emotion_map.values()), "neutral"),
        )

        actions: dict[str, Any] = {
            "expressions": [resolved_expression],
            "expression_decision": decision.to_payload(),
        }
        if planner_error:
            actions["expression_decision_error"] = planner_error
        return actions

    async def _transcribe_audio(self, audio_buffer: np.ndarray) -> str:
        if self._selected_stt_provider is None:
            raise RuntimeError(
                "No STT provider available. Please configure `stt_provider_id` in plugin config or set a default AstrBot STT provider."
            )

        temp_path = _save_audio_buffer_to_temp_wav(audio_buffer)
        try:
            return await self._selected_stt_provider.get_text(temp_path)
        finally:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as exc:
                logger.warning(f"Failed to remove temp STT audio file {temp_path}: {exc}")

    async def _handle_frontend_compat(self, message: dict[str, Any]) -> None:
        msg_type = message.get("type")

        if msg_type == "fetch-backgrounds":
            await self._send_json({"type": "background-files", "files": _list_background_files()})
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
            self._refresh_runtime_settings()
            await self._send_current_model_and_conf(force=True)
        elif msg_type == "heartbeat":
            await self._send_json({"type": "heartbeat-ack"})

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
                self._static_server.stop()
            except Exception as exc:
                logger.warning(f"Failed to close static resource server cleanly: {exc}")

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
            if image_payload.startswith("http://") or image_payload.startswith("https://"):
                return Image.fromURL(url=image_payload)
            if image_payload.startswith("data:"):
                return _image_from_data_uri(image_payload)
            return None

        if not isinstance(image_payload, dict):
            return None

        data = image_payload.get("data")
        mime_type = image_payload.get("mime_type", "image/png")
        if isinstance(data, str) and data:
            if data.startswith("http://") or data.startswith("https://"):
                return Image.fromURL(url=data)
            if data.startswith("data:"):
                return _image_from_data_uri(data)
            return Image.fromBase64(base64=data)
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


def _plugin_config_get(config: Any, key: str, default: Any) -> Any:
    if config is None:
        return default
    if hasattr(config, "get"):
        value = config.get(key, default)
        return default if value is None else value
    return default


def _image_from_data_uri(data_uri: str):
    if ";base64," not in data_uri:
        return None
    _, bs64_data = data_uri.split(";base64,", 1)
    if not bs64_data:
        return None
    return Image.fromBase64(base64=bs64_data)


def _save_audio_buffer_to_temp_wav(audio_buffer: np.ndarray) -> str:
    import wave

    temp_dir = get_astrbot_temp_path()
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"olv_stt_{uuid4().hex}.wav")

    audio = audio_buffer.astype(np.float32)
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767).astype(np.int16)

    with wave.open(temp_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm.tobytes())

    return temp_path


def _parse_model_info(
    raw_model_info: Any,
    host: str,
    http_port: int,
    selected_model_name: str = "",
) -> dict[str, Any]:
    base_url = f"http://{host}:{http_port}"

    if isinstance(raw_model_info, dict):
        if raw_model_info:
            return _normalize_model_info(raw_model_info, base_url)
    if isinstance(raw_model_info, str):
        try:
            parsed = json.loads(raw_model_info)
            if parsed:
                return _normalize_model_info(parsed, base_url)
        except json.JSONDecodeError:
            logger.warning("Invalid `model_info_json`, falling back to empty object.")
    model_dict_path = LIVE2DS_DIR / "model_dict.json"
    if model_dict_path.exists():
        try:
            data = json.loads(model_dict_path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                if selected_model_name:
                    selected = next(
                        (
                            item
                            for item in data
                            if isinstance(item, dict)
                            and item.get("name") == selected_model_name
                        ),
                        None,
                    )
                    if isinstance(selected, dict):
                        return _normalize_model_info(selected, base_url)
                    logger.warning(
                        f"Live2D model `{selected_model_name}` not found in live2ds/model_dict.json, fallback to first model."
                    )

                first = data[0]
                if isinstance(first, dict):
                    return _normalize_model_info(first, base_url)
        except Exception as exc:
            logger.warning(f"Failed to load default model info from live2ds/model_dict.json: {exc}")
    return {}


def _normalize_model_info(model_info: dict[str, Any], base_url: str) -> dict[str, Any]:
    normalized = dict(model_info)
    url = normalized.get("url")
    if isinstance(url, str) and url.startswith("/"):
        normalized["url"] = f"{base_url}{url}"
    return normalized


def _build_static_routes() -> dict[str, Path]:
    return {
        "/live2ds": LIVE2DS_DIR,
        "/bg": OLV_DIR / "backgrounds",
        "/avatars": OLV_DIR / "avatars",
        "/cache": OLV_DIR / "cache",
    }


def _list_background_files() -> list[str]:
    bg_dir = OLV_DIR / "backgrounds"
    if not bg_dir.exists():
        return []
    return sorted(
        [
            entry.name
            for entry in bg_dir.iterdir()
            if entry.is_file() and entry.name.lower() != "readme.md"
        ]
    )
