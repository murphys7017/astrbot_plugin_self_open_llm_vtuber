"""Builders for outbound OLV desktop-pet payloads."""

from __future__ import annotations

from typing import Any

from pydub import AudioSegment
from pydub.utils import make_chunks


def build_set_model_and_conf(
    model_info: dict[str, Any],
    conf_name: str,
    conf_uid: str,
    client_uid: str,
) -> dict[str, Any]:
    return {
        "type": "set-model-and-conf",
        "model_info": model_info,
        "conf_name": conf_name,
        "conf_uid": conf_uid,
        "client_uid": client_uid,
    }


def build_control(text: str) -> dict[str, Any]:
    return {"type": "control", "text": text}


def build_full_text(text: str) -> dict[str, Any]:
    return {"type": "full-text", "text": text}


def build_backend_synth_complete() -> dict[str, Any]:
    return {"type": "backend-synth-complete"}


def build_force_new_message() -> dict[str, Any]:
    return {"type": "force-new-message"}


def build_error(message: str) -> dict[str, Any]:
    return {"type": "error", "message": message}


def build_audio_payload(
    audio_path: str,
    audio_url: str | None,
    text: str,
    speaker_name: str,
    avatar: str,
    action_mapping: dict[str, Any] | None = None,
) -> dict[str, Any]:
    display_text = {"text": text, "name": speaker_name, "avatar": avatar}
    return _prepare_audio_payload(
        audio_path=audio_path,
        audio_url=audio_url,
        display_text=display_text,
        actions=action_mapping,
        forwarded=False,
    )


def _prepare_audio_payload(
    audio_path: str | None,
    audio_url: str | None,
    chunk_length_ms: int = 20,
    display_text: dict[str, Any] | None = None,
    actions: dict[str, Any] | None = None,
    forwarded: bool = False,
) -> dict[str, Any]:
    """Local OLV-compatible audio payload builder to avoid external import coupling."""
    if not audio_path:
        return {
            "type": "audio",
            "audio_url": None,
            "volumes": [],
            "slice_length": chunk_length_ms,
            "display_text": display_text,
            "actions": actions,
            "forwarded": forwarded,
        }

    try:
        audio = AudioSegment.from_file(audio_path)
    except Exception as exc:
        raise ValueError(
            f"Error loading generated audio file '{audio_path}': {exc}"
        ) from exc

    volumes = _get_volume_by_chunks(audio, chunk_length_ms)
    return {
        "type": "audio",
        "audio_url": audio_url,
        "volumes": volumes,
        "slice_length": chunk_length_ms,
        "display_text": display_text,
        "actions": actions,
        "forwarded": forwarded,
    }


def _get_volume_by_chunks(audio: AudioSegment, chunk_length_ms: int) -> list[float]:
    chunks = make_chunks(audio, chunk_length_ms)
    volumes = [chunk.rms for chunk in chunks]
    max_volume = max(volumes)
    if max_volume == 0:
        raise ValueError("Audio is empty or all zero.")
    return [volume / max_volume for volume in volumes]
