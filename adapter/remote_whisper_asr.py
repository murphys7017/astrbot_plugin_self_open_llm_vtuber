from __future__ import annotations

import io
import json
import wave
from typing import Any

import httpx
import numpy as np


class RemoteOpenAIWhisperASR:
    """Minimal multipart-file STT client."""

    def __init__(
        self,
        endpoint_url: str,
        model: str = "",
        api_key: str = "",
        language: str = "",
        prompt: str = "",
        timeout: float = 120.0,
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.language = language
        self.prompt = prompt
        self.timeout = timeout

    async def async_transcribe_np(self, audio: np.ndarray) -> str:
        wav_bytes = _audio_to_wav_bytes(audio)
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data: dict[str, Any] = {}
        if self.model:
            data["model"] = self.model
        if self.language:
            data["language"] = self.language
        if self.prompt:
            data["prompt"] = self.prompt

        files = {
            "file": ("audio.wav", wav_bytes, "audio/wav"),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.endpoint_url,
                headers=headers,
                data=data,
                files=files,
            )
            response.raise_for_status()

        try:
            payload = response.json()
        except json.JSONDecodeError:
            return response.text.strip()

        if isinstance(payload, dict):
            for key in ("text", "transcription", "result", "message"):
                text = payload.get(key, "")
                if isinstance(text, str):
                    return text.strip()
            inner = payload.get("data")
            if isinstance(inner, dict):
                for key in ("text", "transcription", "result"):
                    text = inner.get(key, "")
                    if isinstance(text, str):
                        return text.strip()

        raise ValueError("Remote Whisper response did not contain a valid `text` field.")


def _audio_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)

    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buffer.getvalue()
