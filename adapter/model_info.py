from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astrbot.api import logger


def parse_model_info(
    raw_model_info: Any,
    *,
    host: str,
    http_port: int,
    live2ds_dir: Path,
    selected_model_name: str = "",
) -> dict[str, Any]:
    base_url = f"http://{host}:{http_port}"

    if isinstance(raw_model_info, dict):
        if raw_model_info:
            return normalize_model_info(raw_model_info, base_url)
    if isinstance(raw_model_info, str):
        try:
            parsed = json.loads(raw_model_info)
            if parsed:
                return normalize_model_info(parsed, base_url)
        except json.JSONDecodeError:
            logger.warning("Invalid `model_info_json`, falling back to empty object.")

    model_dict_path = live2ds_dir / "model_dict.json"
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
                        return normalize_model_info(selected, base_url)
                    logger.warning(
                        "Live2D model `%s` not found in live2ds/model_dict.json, fallback to first model.",
                        selected_model_name,
                    )

                first = data[0]
                if isinstance(first, dict):
                    return normalize_model_info(first, base_url)
        except Exception as exc:
            logger.warning(
                "Failed to load default model info from live2ds/model_dict.json: %s",
                exc,
            )
    return {}


def normalize_model_info(model_info: dict[str, Any], base_url: str) -> dict[str, Any]:
    normalized = dict(model_info)
    url = normalized.get("url")
    if isinstance(url, str) and url.startswith("/"):
        normalized["url"] = f"{base_url}{url}"
    return normalized


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
