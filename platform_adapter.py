from __future__ import annotations
"""AstrBot platform adapter for the OLV desktop-pet frontend."""
import asyncio
import base64
import mimetypes
import os
from pathlib import Path
import re
import time
from urllib.parse import unquote
import numpy as np

from astrbot.api.platform import Platform, AstrBotMessage, MessageMember, PlatformMetadata, MessageType
from astrbot.api.message_components import Plain, Image, Record # 消息链中的组件，可以根据需要导入
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.api.platform import register_platform_adapter
from astrbot.api.provider import Provider, STTProvider
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_temp_path
import json
import traceback
from typing import Any
from uuid import uuid4

from pydub import AudioSegment

from .adapter.base_expression_planner import (
    BaseExpressionPlanningError,
    build_fallback_base_expression_decision,
    plan_base_expression,
)
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
AUDIO_CACHE_DIR = OLV_DIR / "cache" / "audio"
IMAGE_CACHE_DIR = OLV_DIR / "cache" / "images"
AUDIO_CACHE_MAX_FILES = 120
AUDIO_CACHE_MAX_AGE_SECONDS = 6 * 60 * 60
AUDIO_CACHE_TRIM_PROTECTION_SECONDS = 10 * 60
FRONTEND_IMAGE_MAX_BYTES = 10 * 1024 * 1024
FRONTEND_IMAGE_ALLOWED_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
}


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
        self._turn_timing: dict[str, Any] = {}
        self._turn_expression_cache: dict[str, Any] = {}
        self.chat_buffer = ChatBuffer(
            maxlen=int(_plugin_config_get(self._plugin_config, "chat_buffer_size", 10))
        )
        self._prepare_audio_cache_dir()
        self._cleanup_audio_cache()

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

        for image_payload in images:
            image_component = self._convert_image_component(image_payload)
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
        abm.raw_message = normalized_raw_message

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
            self._begin_turn_timing(message_obj.message_str)
            self._turn_expression_cache = {}
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
            self._mark_turn_timing("event_committed_at")
            logger.info(
                "Turn timing start: turn=%s text_len=%d",
                self._current_turn_index(),
                len(message_obj.message_str or ""),
            )

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

    def _prepare_audio_cache_dir(self) -> None:
        AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cleanup_audio_cache(self) -> None:
        self._prepare_audio_cache_dir()
        now = time.time()
        cached_files = [
            entry
            for entry in AUDIO_CACHE_DIR.iterdir()
            if entry.is_file()
        ]

        for entry in cached_files:
            try:
                age_seconds = now - entry.stat().st_mtime
            except OSError:
                continue

            if age_seconds <= AUDIO_CACHE_MAX_AGE_SECONDS:
                continue

            try:
                entry.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(f"Failed to remove expired audio cache file `{entry}`: {exc}")

        remaining_files = [
            entry
            for entry in AUDIO_CACHE_DIR.iterdir()
            if entry.is_file()
        ]
        protected_cutoff = now - AUDIO_CACHE_TRIM_PROTECTION_SECONDS
        trimmable_files = sorted(
            (
                entry
                for entry in remaining_files
                if entry.stat().st_mtime <= protected_cutoff
            ),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

        for entry in trimmable_files[AUDIO_CACHE_MAX_FILES:]:
            try:
                entry.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(f"Failed to trim audio cache file `{entry}`: {exc}")

    def _cache_audio_file(self, source_audio_path: str) -> tuple[str, str]:
        self._cleanup_audio_cache()

        source_path = Path(source_audio_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Audio file not found: {source_audio_path}")

        self._prepare_audio_cache_dir()
        cached_filename = f"{uuid4().hex}.wav"
        cached_path = AUDIO_CACHE_DIR / cached_filename

        try:
            audio = AudioSegment.from_file(source_path)
            audio.export(cached_path, format="wav")
        except Exception as exc:
            raise ValueError(
                f"Failed to convert generated audio file `{source_audio_path}` to wav cache: {exc}"
            ) from exc

        audio_url = f"http://{self.host}:{self.http_port}/cache/audio/{cached_filename}"
        return str(cached_path), audio_url

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
        emit_started_at = time.perf_counter()
        self._mark_turn_timing("emit_started_at", emit_started_at)
        texts, picture_paths, record_paths = _extract_outbound_message_parts(message_chain)
        logger.debug(f"Emitting message chain: {message_chain}")

        reply_text = "\n".join(texts).strip()
        has_audio_reply = bool(record_paths)
        if self._should_skip_duplicate_plain_emit(
            reply_text=reply_text,
            has_audio_reply=has_audio_reply,
        ):
            logger.info(
                "Skip duplicate dual-output plain emit: turn=%s text=%s",
                self._current_turn_index(),
                reply_text[:120],
            )
            return

        if reply_text and not has_audio_reply:
            self.chat_buffer.add("assistant", reply_text)
            await self._send_json(build_full_text(reply_text))

        # Build expression actions from reply text
        actions = {}
        expression_started_at = time.perf_counter()
        if reply_text:
            try:
                expr_actions = await self._get_or_build_expression_actions(
                    reply_text=reply_text,
                    has_audio_reply=has_audio_reply,
                )
                if expr_actions:
                    actions.update(expr_actions)
            except Exception as exc:
                logger.warning(f"Failed to build expression actions: {exc}")
        expression_elapsed_ms = (time.perf_counter() - expression_started_at) * 1000.0
        self._mark_turn_timing("expression_completed_at")

        # Add pictures if available
        if picture_paths:
            actions["pictures"] = picture_paths

        # Send actions only if non-empty
        actions_to_send = actions if actions else None

        if has_audio_reply:
            record_path = record_paths[0]
            audio_cache_started_at = time.perf_counter()
            cached_audio_path, audio_url = self._cache_audio_file(record_path)
            audio_cache_elapsed_ms = (time.perf_counter() - audio_cache_started_at) * 1000.0
            await self._send_json(
                build_audio_payload(
                    audio_path=cached_audio_path,
                    audio_url=audio_url,
                    text=reply_text,
                    speaker_name=self.speaker_name,
                    avatar="",
                    action_mapping=actions_to_send,
                )
            )
            self._mark_turn_timing("audio_payload_sent_at")
            await self._send_json(build_backend_synth_complete())
            self.session_state.mark_playing()
            if self._turn_expression_cache:
                self._turn_expression_cache["audio_sent"] = True
            logger.info(
                "Turn timing: turn=%s pipeline_before_emit_ms=%.1f expression_ms=%.1f audio_cache_ms=%.1f total_before_playback_ms=%.1f has_audio=%s pictures=%d",
                self._current_turn_index(),
                self._elapsed_ms("event_committed_at", "emit_started_at"),
                expression_elapsed_ms,
                audio_cache_elapsed_ms,
                self._elapsed_ms("received_at", "audio_payload_sent_at"),
                True,
                len(picture_paths),
            )
            return

        if actions_to_send:
            await self._send_json(
                build_audio_payload(
                    audio_path="",
                    audio_url=None,
                    text=reply_text,
                    speaker_name=self.speaker_name,
                    avatar="",
                    action_mapping=actions_to_send,
                )
            )
            self._mark_turn_timing("audio_payload_sent_at")

        if reply_text:
            self.session_state.reset_to_idle()
            await self._send_json(build_backend_synth_complete())
            await self._send_json(build_force_new_message())
            await self._send_json(build_control("conversation-chain-end"))
            self._mark_turn_timing("turn_completed_at")
            logger.info(
                "Turn timing: turn=%s pipeline_before_emit_ms=%.1f expression_ms=%.1f total_ms=%.1f has_audio=%s pictures=%d",
                self._current_turn_index(),
                self._elapsed_ms("event_committed_at", "emit_started_at"),
                expression_elapsed_ms,
                self._elapsed_ms("received_at", "turn_completed_at"),
                False,
                len(picture_paths),
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

        previous_stt_provider_id = self.stt_provider_id
        previous_expression_provider_id = self.expression_provider_id
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

        provider_config_changed = (
            previous_stt_provider_id != self.stt_provider_id
            or previous_expression_provider_id != self.expression_provider_id
        )
        provider_binding_missing = (
            (self.stt_provider_id and self._selected_stt_provider is None)
            or (not self.stt_provider_id and self._selected_stt_provider is not None)
            or (
                self.expression_provider_id
                and self._selected_expression_provider is None
            )
            or (
                not self.expression_provider_id
                and self._selected_expression_provider is not None
            )
        )
        if provider_config_changed or provider_binding_missing:
            logger.info(
                "Provider runtime settings changed, reloading provider bindings "
                f"(stt: {previous_stt_provider_id or '<default>'} -> {self.stt_provider_id or '<default>'}, "
                f"expression: {previous_expression_provider_id or '<disabled>'} -> "
                f"{self.expression_provider_id or '<disabled>'})"
            )
            self._selected_stt_provider = None
            self._selected_expression_provider = None
            self._load_selected_providers()

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

    def _current_turn_index(self) -> int:
        return int(getattr(self.session_state, "turn_index", 0) or 0)

    def _begin_turn_timing(self, user_text: str) -> None:
        self._turn_timing = {
            "turn_index": self._current_turn_index(),
            "received_at": time.perf_counter(),
            "user_text_len": len(user_text or ""),
        }

    def _mark_turn_timing(
        self,
        key: str,
        value: float | None = None,
    ) -> None:
        if not self._turn_timing:
            self._turn_timing = {"turn_index": self._current_turn_index()}
        self._turn_timing[key] = (
            time.perf_counter() if value is None else value
        )

    def _elapsed_ms(self, start_key: str, end_key: str) -> float:
        start_value = _coerce_perf_counter(self._turn_timing.get(start_key))
        end_value = _coerce_perf_counter(self._turn_timing.get(end_key))
        if start_value is None or end_value is None:
            return -1.0
        return max((end_value - start_value) * 1000.0, 0.0)

    async def _get_or_build_expression_actions(
        self,
        *,
        reply_text: str,
        has_audio_reply: bool,
    ) -> dict[str, Any] | None:
        cache_key = (reply_text or "").strip()
        if not cache_key:
            return None

        cached_reply_text = self._turn_expression_cache.get("reply_text")
        cached_actions = self._turn_expression_cache.get("actions")
        if cached_reply_text == cache_key and isinstance(cached_actions, dict):
            logger.debug(
                "Reusing cached expression actions for turn=%s has_audio=%s",
                self._current_turn_index(),
                has_audio_reply,
            )
            return dict(cached_actions)

        actions = await self._build_expression_actions(cache_key)
        if isinstance(actions, dict):
            self._turn_expression_cache = {
                "reply_text": cache_key,
                "actions": dict(actions),
                "has_audio_reply": has_audio_reply,
                "audio_sent": False,
            }
        return actions

    def _should_skip_duplicate_plain_emit(
        self,
        *,
        reply_text: str,
        has_audio_reply: bool,
    ) -> bool:
        if has_audio_reply:
            return False

        cache_key = (reply_text or "").strip()
        if not cache_key:
            return False

        cached_reply_text = self._turn_expression_cache.get("reply_text")
        cached_has_audio_reply = bool(self._turn_expression_cache.get("has_audio_reply"))
        cached_audio_sent = bool(self._turn_expression_cache.get("audio_sent"))
        return (
            cached_reply_text == cache_key
            and cached_has_audio_reply
            and cached_audio_sent
        )

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
        motion_map = self.model_info.get("motionMap") or {}
        emotion_map_keys = [
            key for key in emotion_map.keys() if isinstance(key, str) and key
        ]
        decision = build_fallback_base_expression_decision(reply_text, emotion_map_keys)
        planner_error = None
        if self._selected_expression_provider is not None:
            try:
                provider_id = self._selected_expression_provider.meta().id
            except Exception:
                provider_id = "<unknown>"
            logger.debug(f"Planning base expression with provider: {provider_id}")
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
                logger.warning(f"Base expression planner validation failed, fallback to neutral: {exc}")
            except Exception as exc:
                planner_error = str(exc)
                logger.warning(f"Base expression planner failed, fallback to neutral: {exc}")

        resolved_expressions = _resolve_action_asset_list(
            emotion_map,
            decision.base_expression,
        )
        resolved_expression = (
            resolved_expressions[0] if resolved_expressions else "neutral"
        )
        resolved_motions = _resolve_action_asset_list(
            motion_map,
            decision.base_expression,
        )

        actions: dict[str, Any] = {
            "expressions": [resolved_expression],
            "expression_decision": decision.to_payload(),
        }
        if resolved_motions:
            actions["motions"] = resolved_motions
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
                await asyncio.to_thread(self._static_server.stop)
            except Exception as exc:
                logger.warning(f"Failed to close static resource server cleanly: {exc}")

    async def _finalize_turn(self) -> None:
        if not self.session_state.waiting_for_playback_complete:
            return
        await self._send_json(build_force_new_message())
        await self._send_json(build_control("conversation-chain-end"))
        self.session_state.mark_playback_complete()
        self._mark_turn_timing("playback_completed_at")
        logger.info(
            "Turn timing playback: turn=%s playback_ms=%.1f total_ms=%.1f",
            self._current_turn_index(),
            self._elapsed_ms("audio_payload_sent_at", "playback_completed_at"),
            self._elapsed_ms("received_at", "playback_completed_at"),
        )

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

    @staticmethod
    def _convert_image_component(image_payload: Any):
        if isinstance(image_payload, str) and image_payload:
            local_path = _save_frontend_image_payload_to_local_path(image_payload)
            if local_path:
                return Image.fromFileSystem(path=local_path)
            if image_payload.startswith("http://") or image_payload.startswith("https://"):
                return Image.fromURL(url=image_payload)
            return None

        if not isinstance(image_payload, dict):
            return None

        data = image_payload.get("data")
        mime_type = image_payload.get("mime_type", "image/png")
        if isinstance(data, str) and data:
            local_path = _save_frontend_image_payload_to_local_path(
                data,
                mime_type=mime_type,
            )
            if local_path:
                return Image.fromFileSystem(path=local_path)
            if data.startswith("http://") or data.startswith("https://"):
                return Image.fromURL(url=data)
        return None


def _iter_message_chain(message_chain) -> list[Any]:
    if message_chain is None:
        return []
    if hasattr(message_chain, "chain") and isinstance(message_chain.chain, list):
        return message_chain.chain
    if isinstance(message_chain, list):
        return message_chain
    return [message_chain]


def _extract_outbound_message_parts(message_chain) -> tuple[list[str], list[str], list[str]]:
    texts: list[str] = []
    picture_paths: list[str] = []
    record_paths: list[str] = []

    for component in _iter_message_chain(message_chain):
        if isinstance(component, Plain) and component.text.strip():
            texts.append(component.text.strip())
            continue

        if isinstance(component, Image):
            image_path = getattr(component, "file", None)
            if isinstance(image_path, str) and image_path:
                picture_paths.append(image_path)
            continue

        if not isinstance(component, Record):
            continue

        record_text = getattr(component, "text", None)
        if isinstance(record_text, str) and record_text.strip():
            texts.append(record_text.strip())

        record_path = getattr(component, "file", None)
        if isinstance(record_path, str) and record_path:
            record_paths.append(record_path)

    return texts, picture_paths, record_paths


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


def _normalize_action_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _normalize_action_asset_list(value: Any) -> list[str]:
    if isinstance(value, str):
        asset = value.strip()
        return [asset] if asset else []
    if isinstance(value, list):
        return [
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        ]
    return []


def _resolve_action_asset_list(asset_map: Any, decision_key: str) -> list[str]:
    if not isinstance(asset_map, dict) or not asset_map:
        return []

    normalized_key = _normalize_action_key(decision_key)
    if normalized_key:
        for key, value in asset_map.items():
            if _normalize_action_key(key) == normalized_key:
                return _normalize_action_asset_list(value)

    for value in asset_map.values():
        normalized_assets = _normalize_action_asset_list(value)
        if normalized_assets:
            return normalized_assets

    return []


def _image_from_data_uri(data_uri: str):
    if ";base64," not in data_uri:
        return None
    _, bs64_data = data_uri.split(";base64,", 1)
    if not bs64_data:
        return None
    return Image.fromBase64(base64=bs64_data)


def _coerce_perf_counter(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _save_frontend_image_payload_to_local_path(
    image_payload: str,
    *,
    mime_type: str | None = None,
) -> str | None:
    payload = (image_payload or "").strip()
    if not payload:
        return None

    if payload.startswith("file:///"):
        source_path = Path(unquote(payload.replace("file:///", "", 1)))
        return _copy_allowed_frontend_image_to_cache(source_path, mime_type)

    if os.path.exists(payload):
        return _copy_allowed_frontend_image_to_cache(Path(payload), mime_type)

    if payload.startswith("http://") or payload.startswith("https://"):
        return None

    image_bytes: bytes | None = None
    resolved_mime_type = mime_type or "image/png"

    if payload.startswith("data:"):
        data_match = re.match(
            r"^data:(?P<mime>[\w.+-]+/[\w.+-]+);base64,(?P<data>.+)$",
            payload,
            re.DOTALL,
        )
        if not data_match:
            logger.warning("Unsupported frontend image data URI, skip saving image.")
            return None
        resolved_mime_type = data_match.group("mime") or resolved_mime_type
        try:
            image_bytes = base64.b64decode(data_match.group("data"))
        except Exception as exc:
            logger.warning(f"Failed to decode frontend image data URI: {exc}")
            return None
    else:
        compact_payload = payload
        if compact_payload.startswith("base64://"):
            compact_payload = compact_payload.removeprefix("base64://")
        try:
            image_bytes = base64.b64decode(compact_payload)
        except Exception:
            return None

    return _write_frontend_image_bytes(image_bytes, resolved_mime_type)


def _write_frontend_image_bytes(image_bytes: bytes | None, mime_type: str) -> str | None:
    if not image_bytes:
        return None

    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    suffix = mimetypes.guess_extension(mime_type or "") or ".png"
    if suffix == ".jpe":
        suffix = ".jpg"

    image_path = IMAGE_CACHE_DIR / f"frontend_{uuid4().hex}{suffix}"
    image_path.write_bytes(image_bytes)
    logger.debug(f"Saved frontend image to local file: {image_path}")
    return str(image_path.resolve())


def _copy_allowed_frontend_image_to_cache(
    source_path: Path,
    mime_type: str | None = None,
) -> str | None:
    try:
        resolved_path = source_path.expanduser().resolve(strict=True)
    except OSError:
        return None

    if not resolved_path.is_file():
        return None

    if not _is_allowed_frontend_image_path(resolved_path):
        logger.warning(f"Rejected frontend local image path outside allowed roots: {resolved_path}")
        return None

    if resolved_path.suffix.lower() not in FRONTEND_IMAGE_ALLOWED_SUFFIXES:
        logger.warning(f"Rejected frontend local image path with unsupported suffix: {resolved_path}")
        return None

    try:
        image_bytes = resolved_path.read_bytes()
    except OSError as exc:
        logger.warning(f"Failed to read frontend local image `{resolved_path}`: {exc}")
        return None

    if not image_bytes:
        return None

    if len(image_bytes) > FRONTEND_IMAGE_MAX_BYTES:
        logger.warning(f"Rejected frontend image larger than {FRONTEND_IMAGE_MAX_BYTES} bytes: {resolved_path}")
        return None

    resolved_mime_type = mime_type or mimetypes.guess_type(str(resolved_path))[0] or "image/png"
    return _write_frontend_image_bytes(image_bytes, resolved_mime_type)


def _is_allowed_frontend_image_path(path: Path) -> bool:
    for root in _frontend_image_allowed_roots():
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _frontend_image_allowed_roots() -> tuple[Path, ...]:
    temp_root = Path(get_astrbot_temp_path()).resolve()
    return (
        IMAGE_CACHE_DIR.resolve(),
        LIVE2DS_DIR.resolve(),
        (OLV_DIR / "avatars").resolve(),
        (OLV_DIR / "backgrounds").resolve(),
        temp_root,
    )


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
