from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


LIVE2D_BASE_EXPRESSION_EXTRA_KEY = "live2d_base_expression"
LIVE2D_MOTION_ID_EXTRA_KEY = "live2d_motion_id"
_JSON_FILE_CACHE: dict[tuple[str, int, int], Any] = {}

_BASE_EXPRESSION_TAG_PATTERN = re.compile(
    r"^\s*<~(?P<base_expression>[^~<>\r\n]{1,64})~>\s*"
)
_ANIM_TAG_PREFIXES = ("<@anim", "<@motion")


def collect_available_base_expressions(
    *,
    live2ds_dir: Path,
    selected_model_name: str = "",
) -> list[str]:
    model_dict_path = live2ds_dir / "model_dict.json"
    if not model_dict_path.exists():
        return []

    try:
        data = _load_json_file_cached(model_dict_path)
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


def collect_available_motion_ids(
    *,
    live2ds_dir: Path,
    selected_model_name: str = "",
) -> list[str]:
    model_dict_path = live2ds_dir / "model_dict.json"
    if not model_dict_path.exists():
        return []

    try:
        data = _load_json_file_cached(model_dict_path)
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

    motion_map = selected_model.get("motionMap")
    if not isinstance(motion_map, dict):
        return []

    ordered_keys: list[str] = []
    seen_keys: set[str] = set()

    catalog_asset_map = collect_motion_catalog_asset_map(
        live2ds_dir=live2ds_dir,
        selected_model_name=selected_model_name,
    )
    for raw_key in catalog_asset_map.keys():
        normalized_key = normalize_motion_id(raw_key)
        if not normalized_key or normalized_key in seen_keys:
            continue
        seen_keys.add(normalized_key)
        ordered_keys.append(normalized_key)

    for raw_key in motion_map.keys():
        normalized_key = normalize_motion_id(raw_key)
        if not normalized_key or normalized_key in seen_keys:
            continue
        seen_keys.add(normalized_key)
        ordered_keys.append(normalized_key)
    return ordered_keys


def select_motion_candidates(
    motion_ids: list[str],
    *,
    max_candidates: int = 8,
) -> list[str]:
    if not motion_ids:
        return []

    normalized_ids = [
        normalize_motion_id(item)
        for item in motion_ids
        if isinstance(item, str) and normalize_motion_id(item)
    ]
    if not normalized_ids:
        return []

    if max_candidates <= 0 or len(normalized_ids) <= max_candidates:
        return _dedupe_preserve_order(normalized_ids)

    # If catalog-style ids are present (e.g. smirk_tilt, serious_explain),
    # prefer catalog order directly to preserve curated motion semantics.
    catalog_like_count = 0
    for motion_id in normalized_ids:
        if "_" in motion_id and motion_id not in {"sadness", "surprised"}:
            catalog_like_count += 1
    if catalog_like_count >= max_candidates:
        preferred_catalog_order = [
            "gentle_nod",
            "thinking_pause",
            "smirk_tilt",
            "embarrassed_lookaway",
            "annoyed_lean",
            "surprised_backoff",
            "confused_tilt",
            "serious_explain",
            "happy_sway",
            "sad_standard",
            "angry_standard",
            "neutral_peaceful",
        ]
        selected: list[str] = []
        seen: set[str] = set()

        for key in preferred_catalog_order:
            if key in normalized_ids and key not in seen:
                selected.append(key)
                seen.add(key)
                if len(selected) >= max_candidates:
                    return selected

        for key in normalized_ids:
            if key in seen:
                continue
            selected.append(key)
            seen.add(key)
            if len(selected) >= max_candidates:
                break
        return selected

    preferred_order = [
        "neutral",
        "happy",
        "joy",
        "smirk",
        "embarrassed",
        "thinking",
        "confused",
        "sad",
        "sadness",
        "fear",
        "surprise",
        "surprised",
        "anger",
        "angry",
    ]
    selected: list[str] = []
    seen: set[str] = set()

    for key in preferred_order:
        if key in normalized_ids and key not in seen:
            selected.append(key)
            seen.add(key)
            if len(selected) >= max_candidates:
                return selected

    for key in normalized_ids:
        if key in seen:
            continue
        selected.append(key)
        seen.add(key)
        if len(selected) >= max_candidates:
            break

    return selected


def collect_motion_catalog_descriptions(
    *,
    live2ds_dir: Path,
    selected_model_name: str = "",
) -> dict[str, str]:
    entries = collect_motion_catalog_entries(
        live2ds_dir=live2ds_dir,
        selected_model_name=selected_model_name,
    )
    descriptions: dict[str, str] = {}
    for item in entries:
        motion_id = normalize_motion_id(item.get("id"))
        if not motion_id:
            continue
        description = str(item.get("description", "")).strip()
        if not description:
            description = str(item.get("label", "")).strip()
        if description:
            descriptions[motion_id] = description
    return descriptions


def collect_motion_catalog_asset_map(
    *,
    live2ds_dir: Path,
    selected_model_name: str = "",
) -> dict[str, str]:
    entries = collect_motion_catalog_entries(
        live2ds_dir=live2ds_dir,
        selected_model_name=selected_model_name,
    )
    asset_map: dict[str, str] = {}
    for item in entries:
        motion_id = normalize_motion_id(item.get("id"))
        motion_file = str(item.get("file", "")).strip()
        if not motion_id or not motion_file:
            continue
        asset_map[motion_id] = motion_file
    return asset_map


def collect_motion_catalog_entries(
    *,
    live2ds_dir: Path,
    selected_model_name: str = "",
) -> list[dict[str, str]]:
    payload = _load_motion_catalog_payload(
        live2ds_dir=live2ds_dir,
        selected_model_name=selected_model_name,
    )
    return _parse_motion_catalog_entries(payload)


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


def build_inline_anim_hook_prompt(
    *,
    motion_candidates: list[str],
    base_expressions: list[str],
    motion_descriptions: dict[str, str] | None = None,
) -> str:
    motion_candidates = _dedupe_preserve_order(
        [normalize_motion_id(item) for item in motion_candidates]
    )
    base_expressions = _dedupe_preserve_order(
        [normalize_base_expression_key(item) for item in base_expressions]
    )
    if not motion_candidates and not base_expressions:
        return ""

    motion_line = ", ".join(motion_candidates) if motion_candidates else "(空)"
    base_line = ", ".join(base_expressions) if base_expressions else "(空)"
    normalized_descriptions: dict[str, str] = {}
    if isinstance(motion_descriptions, dict):
        for key, value in motion_descriptions.items():
            normalized_key = normalize_motion_id(key)
            if not normalized_key or not isinstance(value, str):
                continue
            desc = value.strip()
            if not desc:
                continue
            normalized_descriptions[normalized_key] = desc

    prompt = (
        "\n\n[Live2D Motion Decision]\n"
        "在你的最终回答最开头，必须单独输出一个动作决策标签。\n"
        '格式严格为：<@anim {"motion_id":"...","base_expression":"..."}>\n'
        f"motion_id 只能从以下候选中选择：{motion_line}\n"
        f"base_expression 只能从以下候选中选择：{base_line}\n"
    )

    if motion_candidates and normalized_descriptions:
        described_lines = []
        for motion_id in motion_candidates:
            desc = normalized_descriptions.get(motion_id)
            if not desc:
                continue
            described_lines.append(f"- {motion_id}: {desc}")
        if described_lines:
            prompt += (
                "候选动作语义说明（仅供选择参考）：\n"
                + "\n".join(described_lines)
                + "\n"
            )

    prompt += (
        "如果你不确定 motion_id，可输出空字符串 \"\"，但 base_expression 必须尽量给出。\n"
        '输出示例：<@anim {"motion_id":"thinking","base_expression":"confused"}>\n'
        "紧接着正常输出正文内容。\n"
        "整个回复中只允许出现一次动作决策标签。\n"
        "正文后续绝对不要再次输出任何 <@anim ...>、<@motion ...> 或类似标签。\n"
        "正文只能保留一段自然回复，不要再追加第二段补充、吐槽或总结。\n"
        "如果用户当前输入不是空消息，绝对不要臆测用户发送了空消息，也不要提及空消息、手滑、重复发送等内容。"
    )
    return prompt


def extract_inline_anim_decision(
    text: str,
    *,
    allowed_motion_ids: list[str] | None = None,
    allowed_base_expressions: list[str] | None = None,
) -> tuple[dict[str, str] | None, str]:
    raw_text = text or ""
    parsed_payloads, cleaned_text = _extract_all_inline_anim_payloads(raw_text)
    anim_tag_consumed = cleaned_text != raw_text

    allowed_motion = _normalized_set(allowed_motion_ids)
    allowed_base = _normalized_set(allowed_base_expressions)

    for parsed_payload in parsed_payloads:
        motion_id = normalize_motion_id(parsed_payload.get("motion_id"))
        base_expression = normalize_base_expression_key(
            parsed_payload.get("base_expression")
        )

        if allowed_motion and motion_id and motion_id not in allowed_motion:
            motion_id = ""
        if allowed_base and base_expression and base_expression not in allowed_base:
            base_expression = ""

        result: dict[str, str] = {}
        if motion_id:
            result["motion_id"] = motion_id
        if base_expression:
            result["base_expression"] = base_expression
        if result:
            return result, cleaned_text

    base_source = cleaned_text if anim_tag_consumed else raw_text
    base_expression, cleaned_by_base = extract_inline_base_expression(
        base_source,
        allowed_base_expressions=allowed_base_expressions,
    )
    if base_expression:
        return {"base_expression": base_expression}, cleaned_by_base
    return None, base_source


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


def normalize_motion_id(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _extract_inline_anim_payload(text: str) -> tuple[dict[str, Any] | None, str]:
    raw_text = text or ""
    lstripped = raw_text.lstrip()
    leading_ws_len = len(raw_text) - len(lstripped)
    lowered = lstripped.lower()

    matched_prefix = None
    for prefix in _ANIM_TAG_PREFIXES:
        if lowered.startswith(prefix):
            matched_prefix = prefix
            break
    if matched_prefix is None:
        return None, raw_text

    idx = len(matched_prefix)
    while idx < len(lstripped) and lstripped[idx].isspace():
        idx += 1

    if idx >= len(lstripped) or lstripped[idx] != "{":
        return None, raw_text

    payload_end = _find_json_object_end(lstripped, idx)
    if payload_end < 0:
        return None, raw_text

    payload_str = lstripped[idx : payload_end + 1]
    tail_idx = payload_end + 1
    while tail_idx < len(lstripped) and lstripped[tail_idx].isspace():
        tail_idx += 1

    if tail_idx >= len(lstripped) or lstripped[tail_idx] != ">":
        return None, raw_text

    try:
        payload = json.loads(payload_str)
    except Exception:
        payload = None

    cleaned = raw_text[leading_ws_len + tail_idx + 1 :].lstrip()
    if isinstance(payload, dict):
        return payload, cleaned
    return None, cleaned


def strip_inline_expression_markup(text: str) -> str:
    cleaned = _extract_all_inline_anim_payloads(text or "")[1]
    base_expression, cleaned = extract_inline_base_expression(cleaned)
    del base_expression
    return _normalize_inline_markup_whitespace(cleaned)


def _extract_all_inline_anim_payloads(text: str) -> tuple[list[dict[str, Any]], str]:
    raw_text = text or ""
    payloads: list[dict[str, Any]] = []
    text_segments: list[str] = []
    cursor = 0
    lowered = raw_text.lower()
    found_any_tag = False

    while cursor < len(raw_text):
        next_positions = [
            lowered.find(prefix, cursor)
            for prefix in _ANIM_TAG_PREFIXES
            if lowered.find(prefix, cursor) >= 0
        ]
        if not next_positions:
            if not found_any_tag:
                text_segments.append(raw_text[cursor:])
            elif payloads:
                text_segments.append(raw_text[cursor:])
            break

        tag_start = min(next_positions)
        if found_any_tag and payloads:
            text_segments.append(raw_text[cursor:tag_start])
            break

        if not found_any_tag:
            leading_text = raw_text[cursor:tag_start]
            if leading_text.strip():
                text_segments.append(leading_text)

        payload, tag_end = _parse_inline_anim_tag(raw_text, tag_start)
        if tag_end < 0:
            if not found_any_tag:
                text_segments.append(raw_text[tag_start])
            cursor = tag_start + 1
            continue

        found_any_tag = True
        if isinstance(payload, dict):
            payloads.append(payload)
        cursor = tag_end

    cleaned = _normalize_inline_markup_whitespace("".join(text_segments))
    return payloads, cleaned


def _parse_inline_anim_tag(text: str, start_index: int) -> tuple[dict[str, Any] | None, int]:
    raw_text = text or ""
    if start_index < 0 or start_index >= len(raw_text):
        return None, -1

    lowered = raw_text.lower()
    matched_prefix = None
    for prefix in _ANIM_TAG_PREFIXES:
        if lowered.startswith(prefix, start_index):
            matched_prefix = prefix
            break
    if matched_prefix is None:
        return None, -1

    idx = start_index + len(matched_prefix)
    while idx < len(raw_text) and raw_text[idx].isspace():
        idx += 1

    if idx >= len(raw_text) or raw_text[idx] != "{":
        return None, -1

    payload_end = _find_json_object_end(raw_text, idx)
    if payload_end < 0:
        return None, -1

    payload_str = raw_text[idx : payload_end + 1]
    tail_idx = payload_end + 1
    while tail_idx < len(raw_text) and raw_text[tail_idx].isspace():
        tail_idx += 1

    if tail_idx >= len(raw_text) or raw_text[tail_idx] != ">":
        return None, -1

    try:
        payload = json.loads(payload_str)
    except Exception:
        payload = None

    end_index = tail_idx + 1
    while end_index < len(raw_text) and raw_text[end_index].isspace():
        end_index += 1

    return payload if isinstance(payload, dict) else None, end_index


def _normalize_inline_markup_whitespace(text: str) -> str:
    cleaned = text.replace("\r\n", "\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _find_json_object_end(text: str, start_index: int) -> int:
    in_string = False
    escaped = False
    depth = 0

    for idx in range(start_index, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = False
                continue
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return idx
            if depth < 0:
                return -1
            continue

    return -1


def _normalized_set(values: list[str] | None) -> set[str]:
    if not values:
        return set()
    return {
        normalize_base_expression_key(item)
        for item in values
        if isinstance(item, str) and normalize_base_expression_key(item)
    }


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _resolve_default_model_name(live2ds_dir: Path) -> str:
    model_dict_path = live2ds_dir / "model_dict.json"
    if not model_dict_path.exists():
        return ""
    try:
        payload = _load_json_file_cached(model_dict_path)
    except Exception:
        return ""
    if not isinstance(payload, list) or not payload:
        return ""
    first = payload[0]
    if not isinstance(first, dict):
        return ""
    model_name = first.get("name")
    if not isinstance(model_name, str):
        return ""
    return model_name.strip()


def _load_motion_catalog_payload(
    *,
    live2ds_dir: Path,
    selected_model_name: str = "",
) -> Any:
    model_name = selected_model_name.strip()
    if not model_name:
        model_name = _resolve_default_model_name(live2ds_dir)

    candidate_paths: list[Path] = []
    if model_name:
        candidate_paths.extend(
            [
                live2ds_dir / model_name / "motion_catalog.json",
                live2ds_dir / model_name / "motion-catalog.json",
            ]
        )
    candidate_paths.extend(
        [
            live2ds_dir / "motion_catalog.json",
            live2ds_dir / "motion-catalog.json",
        ]
    )

    for path in candidate_paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            payload = _load_json_file_cached(path)
        except Exception:
            continue
        if payload is not None:
            return payload
    return None


def _load_json_file_cached(path: Path) -> Any:
    stat = path.stat()
    cache_key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    if cache_key in _JSON_FILE_CACHE:
        return _JSON_FILE_CACHE[cache_key]

    payload = json.loads(path.read_text(encoding="utf-8"))
    _JSON_FILE_CACHE[cache_key] = payload
    return payload


def _parse_motion_catalog_payload(payload: Any) -> dict[str, str]:
    if isinstance(payload, dict) and isinstance(payload.get("motions"), list):
        payload = payload.get("motions")

    if isinstance(payload, dict):
        result: dict[str, str] = {}
        for raw_key, raw_value in payload.items():
            key = normalize_motion_id(raw_key)
            if not key:
                continue
            desc = _extract_catalog_description(raw_value)
            if desc:
                result[key] = desc
        return result

    if isinstance(payload, list):
        result: dict[str, str] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            key = normalize_motion_id(
                item.get("motion_id") or item.get("id") or item.get("key")
            )
            if not key:
                continue
            desc = _extract_catalog_description(item)
            if desc:
                result[key] = desc
        return result

    return {}


def _extract_catalog_description(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    for field in ("description", "desc", "semantic", "label", "name"):
        raw = value.get(field)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _parse_motion_catalog_entries(payload: Any) -> list[dict[str, str]]:
    if isinstance(payload, dict) and isinstance(payload.get("motions"), list):
        payload = payload.get("motions")

    entries: list[dict[str, str]] = []
    if not isinstance(payload, list):
        return entries

    for item in payload:
        if not isinstance(item, dict):
            continue
        motion_id = normalize_motion_id(
            item.get("motion_id") or item.get("id") or item.get("key")
        )
        if not motion_id:
            continue
        motion_file = str(item.get("file", "")).strip()
        description = _extract_catalog_description(item)
        label = str(item.get("label", "")).strip()
        entries.append(
            {
                "id": motion_id,
                "file": motion_file,
                "description": description,
                "label": label,
            }
        )
    return entries
