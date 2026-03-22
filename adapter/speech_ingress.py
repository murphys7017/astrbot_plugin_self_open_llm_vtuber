from __future__ import annotations

from collections import Counter
import os
import re
from typing import Any

import numpy as np

from astrbot.api import logger

from .payload_builder import build_control, build_error


class SpeechIngressService:
    def __init__(
        self,
        *,
        media_service,
        runtime_state,
        ensure_vad_engine,
        send_json,
        build_message_object,
    ) -> None:
        self.media_service = media_service
        self.runtime_state = runtime_state
        self._ensure_vad_engine = ensure_vad_engine
        self._send_json = send_json
        self._build_message_object = build_message_object

    async def handle_audio_data(self, message: dict[str, Any]) -> None:
        audio_data = message.get("audio", [])
        if not isinstance(audio_data, list) or not audio_data:
            return

        chunk = np.array(audio_data, dtype=np.float32)
        await self.media_service.append_audio_chunk(chunk)

    async def handle_raw_audio_data(self, message: dict[str, Any]) -> None:
        audio_data = message.get("audio", [])
        if not isinstance(audio_data, list) or not audio_data:
            return

        try:
            vad_engine = self._ensure_vad_engine()
        except Exception as exc:
            logger.error("Failed to initialize VAD engine: %s", exc)
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
                await self.media_service.append_audio_chunk(chunk)
                await self._send_json(build_control("mic-audio-end"))

    async def handle_audio_end(self, message: dict[str, Any]):
        audio_buffer = await self.media_service.drain_audio_buffer()

        if audio_buffer.size == 0:
            logger.debug("Ignoring `mic-audio-end` with empty buffer.")
            return None

        try:
            text = (await self._transcribe_audio(audio_buffer)).strip()
        except Exception as exc:
            logger.error("Audio transcription failed: %s", exc)
            await self._send_json(build_error(f"Audio transcription failed: {exc}"))
            return None

        if not text:
            await self._send_json(build_error("The LLM can't hear you."))
            return None

        should_drop, drop_reason = should_drop_transcription(text)
        if should_drop:
            logger.info("Dropped transcription `%s`: %s", text, drop_reason)
            return None

        await self._send_json({"type": "user-input-transcription", "text": text})

        raw_message = dict(message)
        raw_message["transcription"] = text
        raw_message["audio_sample_count"] = int(audio_buffer.size)
        return self._build_message_object(text=text, raw_message=raw_message)

    async def _transcribe_audio(self, audio_buffer: np.ndarray) -> str:
        if self.runtime_state.selected_stt_provider is None:
            raise RuntimeError(
                "No STT provider available. Please configure `stt_provider_id` in plugin config or set a default AstrBot STT provider."
            )

        temp_path = self.media_service.save_audio_buffer_to_temp_wav(audio_buffer)
        try:
            return await self.runtime_state.selected_stt_provider.get_text(temp_path)
        finally:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as exc:
                logger.warning("Failed to remove temp STT audio file %s: %s", temp_path, exc)


def should_drop_transcription(text: str) -> tuple[bool, str]:
    normalized = (text or "").strip()
    if not normalized:
        return True, "empty transcription"

    compact = re.sub(r"\s+", "", normalized)
    if not compact:
        return True, "empty transcription after whitespace cleanup"

    meaningful_chars = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", compact)
    if len(meaningful_chars) < 2:
        return True, "meaningful character count < 2"

    allowed_symbol_pattern = r"[\u4e00-\u9fffA-Za-z0-9，。！？；：、,.!?;:'\"“”‘’（）()《》【】\-_~ ]"
    noisy_chars = [
        ch for ch in compact
        if not re.match(allowed_symbol_pattern, ch)
    ]
    noisy_ratio = len(noisy_chars) / max(len(compact), 1)
    if len(compact) >= 4 and noisy_ratio >= 0.45:
        return True, f"noisy char ratio too high ({noisy_ratio:.2f})"

    alnum_or_cjk = "".join(meaningful_chars)
    if len(alnum_or_cjk) >= 4:
        char_counter = Counter(alnum_or_cjk)
        most_common_count = char_counter.most_common(1)[0][1]
        if most_common_count / len(alnum_or_cjk) >= 0.8:
            return True, "repeated character spam"

    if re.fullmatch(r"([A-Za-z0-9\u4e00-\u9fff])\1{3,}", alnum_or_cjk):
        return True, "single-character repetition"

    return False, ""
