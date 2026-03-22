from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astrbot.api import logger

DEFAULT_LIVE2D_MODEL_NAME = "Mk6_1.0"


def parse_model_info(
    raw_model_info: Any,
    *,
    host: str,
    http_port: int,
    live2ds_dir: Path,
    selected_model_name: str = "",
) -> dict[str, Any]:
    base_url = f"http://{host}:{http_port}"
    normalized_selected_model_name = _normalize_model_name(selected_model_name)
    model_dict_entries = _load_model_dict_entries(live2ds_dir)
    parsed_raw_model_info = _parse_raw_model_info(raw_model_info)

    if normalized_selected_model_name:
        selected = _find_model_entry(model_dict_entries, normalized_selected_model_name)
        if isinstance(selected, dict):
            if isinstance(parsed_raw_model_info, dict):
                raw_name = _normalize_model_name(parsed_raw_model_info.get("name"))
                if raw_name and raw_name != normalized_selected_model_name:
                    logger.warning(
                        "Ignoring platform `model_info_json` model `%s` because plugin "
                        "`live2d_model_name` is `%s`.",
                        raw_name,
                        normalized_selected_model_name,
                    )
            return normalize_model_info(selected, base_url)

        logger.warning(
            "Live2D model `%s` not found in live2ds/model_dict.json, fallback to platform "
            "`model_info_json` or first model.",
            normalized_selected_model_name,
        )

    if isinstance(parsed_raw_model_info, dict):
        return normalize_model_info(parsed_raw_model_info, base_url)

    if model_dict_entries:
        first = model_dict_entries[0]
        if isinstance(first, dict):
            return normalize_model_info(first, base_url)
    return {}


def normalize_model_info(model_info: dict[str, Any], base_url: str) -> dict[str, Any]:
    normalized = dict(model_info)
    url = normalized.get("url")
    if isinstance(url, str) and url.startswith("/"):
        normalized["url"] = f"{base_url}{url}"
    return normalized


def _load_model_dict_entries(live2ds_dir: Path) -> list[dict[str, Any]]:
    model_dict_path = live2ds_dir / "model_dict.json"
    if not model_dict_path.exists():
        return []

    try:
        data = json.loads(model_dict_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(
            "Failed to load default model info from live2ds/model_dict.json: %s",
            exc,
        )
        return []

    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _parse_raw_model_info(raw_model_info: Any) -> dict[str, Any] | None:
    if isinstance(raw_model_info, dict):
        return raw_model_info or None
    if isinstance(raw_model_info, str):
        try:
            parsed = json.loads(raw_model_info)
        except json.JSONDecodeError:
            logger.warning("Invalid `model_info_json`, falling back to empty object.")
            return None
        if isinstance(parsed, dict) and parsed:
            return parsed
    return None


def _find_model_entry(
    entries: list[dict[str, Any]],
    model_name: str,
) -> dict[str, Any] | None:
    normalized_target = _normalize_model_name(model_name)
    if not normalized_target:
        return None
    return next(
        (
            item
            for item in entries
            if _normalize_model_name(item.get("name")) == normalized_target
        ),
        None,
    )


def _normalize_model_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def build_static_routes(
    *,
    live2ds_dir: Path,
    olv_dir: Path,
    runtime_cache_dir: Path,
) -> dict[str, Path]:
    return {
        "/live2ds": live2ds_dir,
        "/bg": olv_dir / "backgrounds",
        "/avatars": olv_dir / "avatars",
        "/cache": runtime_cache_dir,
    }


def list_background_files(olv_dir: Path) -> list[str]:
    bg_dir = olv_dir / "backgrounds"
    if not bg_dir.exists():
        return []
    return sorted(
        [
            entry.name
            for entry in bg_dir.iterdir()
            if entry.is_file() and entry.name.lower() != "readme.md"
        ]
    )
