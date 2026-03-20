from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


LIVE2D_BASE_EXPRESSION_EXTRA_KEY = "live2d_base_expression"

_BASE_EXPRESSION_TAG_PATTERN = re.compile(
    r"^\s*<~(?P<base_expression>[^~<>\r\n]{1,64})~>\s*"
)


def collect_available_base_expressions(
    *,
    live2ds_dir: Path,
    selected_model_name: str = "",
) -> list[str]:
    model_dict_path = live2ds_dir / "model_dict.json"
    if not model_dict_path.exists():
        return []

    try:
        data = json.loads(model_dict_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(data, list) or not data:
        return []

    selected_model = None
    if selected_model_name:
        selected_model = next(
            (
                item
                for item in data
                if isinstance(item, dict) and item.get("name") == selected_model_name
            ),
            None,
        )

    if not isinstance(selected_model, dict):
        selected_model = data[0] if isinstance(data[0], dict) else None
    if not isinstance(selected_model, dict):
        return []

    ordered_keys: list[str] = []
    seen_keys: set[str] = set()
    for asset_map_name in ("motionMap", "emotionMap"):
        asset_map = selected_model.get(asset_map_name)
        if not isinstance(asset_map, dict):
            continue
        for raw_key in asset_map.keys():
            normalized_key = normalize_base_expression_key(raw_key)
            if not normalized_key or normalized_key in seen_keys:
                continue
            seen_keys.add(normalized_key)
            ordered_keys.append(normalized_key)
    return ordered_keys


def build_base_expression_hook_prompt(base_expressions: list[str]) -> str:
    if not base_expressions:
        return ""

    joined_keys = ", ".join(base_expressions)
    return (
        "\n\n[Live2D Base Expression]\n"
        "在你的最终回答最开头，必须单独输出一个基础表情标签，格式严格为 <~base_expression~>。\n"
        f"base_expression 只能从以下候选中选择：{joined_keys}\n"
        "输出格式示例：<~neutral~>\n"
        "紧接着正常输出正文内容，不要解释这个标签，不要输出多个标签。"
    )


def extract_inline_base_expression(
    text: str,
    *,
    allowed_base_expressions: list[str] | None = None,
) -> tuple[str | None, str]:
    raw_text = text or ""
    match = _BASE_EXPRESSION_TAG_PATTERN.match(raw_text)
    if match is None:
        return None, raw_text

    base_expression = normalize_base_expression_key(match.group("base_expression"))
    if not base_expression:
        return None, raw_text

    if allowed_base_expressions:
        allowed = {
            normalize_base_expression_key(item)
            for item in allowed_base_expressions
            if isinstance(item, str)
        }
        if base_expression not in allowed:
            return None, raw_text

    cleaned_text = raw_text[match.end() :].lstrip()
    return base_expression, cleaned_text


def normalize_base_expression_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()
