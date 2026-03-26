from __future__ import annotations

from typing import Any

from astrbot.api import logger

from .base_expression_planner import (
    BaseExpressionDecision,
    build_fallback_base_expression_decision,
)
from .inline_expression import (
    collect_motion_catalog_asset_map,
    normalize_base_expression_key,
    normalize_motion_id,
)


async def build_expression_actions(
    *,
    runtime_state,
    chat_buffer,
    last_user_text: str,
    reply_text: str,
    inline_base_expression: str | None = None,
    inline_motion_id: str | None = None,
) -> dict[str, Any] | None:
    if not reply_text:
        return None

    emotion_map = runtime_state.model_info.get("emotionMap") or {}
    motion_map = runtime_state.model_info.get("motionMap") or {}
    motion_catalog_map = collect_motion_catalog_asset_map(
        live2ds_dir=runtime_state.live2ds_dir,
        selected_model_name=runtime_state.live2d_model_name,
    )
    action_map_keys = collect_action_map_keys(motion_map, emotion_map)
    motion_map_keys = collect_action_map_keys(motion_map)
    motion_catalog_keys = collect_action_map_keys(motion_catalog_map)
    if not action_map_keys:
        logger.warning("No action keys found in model_info motionMap/emotionMap, fallback to neutral.")
        return {
            "expressions": ["neutral"],
            "expression_decision": {
                "semantic_expression": "neutral",
                "base_expression": "neutral",
                "reason": "empty action map keys",
            },
        }

    normalized_inline_expression = normalize_base_expression_key(inline_base_expression)
    normalized_inline_motion = normalize_motion_id(inline_motion_id)
    decision_source = "fallback"
    motion_error = None
    motion_source = ""

    if normalized_inline_expression and normalized_inline_expression in action_map_keys:
        decision = BaseExpressionDecision(
            semantic_expression=normalized_inline_expression,
            base_expression=normalized_inline_expression,
            reason="inline llm tag",
        )
        decision_source = "inline_tag"
    else:
        decision = build_fallback_base_expression_decision(reply_text, action_map_keys)

    resolved_motions: list[str] = []
    if normalized_inline_motion:
        if normalized_inline_motion in motion_catalog_keys:
            resolved_motions = resolve_action_asset_list(
                motion_catalog_map,
                normalized_inline_motion,
                allow_fallback=False,
            )
            if resolved_motions:
                motion_source = "inline_motion_catalog_id"
            else:
                motion_error = (
                    f"inline motion_id `{normalized_inline_motion}` exists in motion_catalog but has no usable file."
                )
        elif normalized_inline_motion in motion_map_keys:
            resolved_motions = resolve_action_asset_list(
                motion_map,
                normalized_inline_motion,
                allow_fallback=False,
            )
            if resolved_motions:
                motion_source = "inline_motion_id"
            else:
                motion_error = (
                    f"inline motion_id `{normalized_inline_motion}` has no usable motion assets."
                )
        else:
            motion_error = (
                "inline motion_id "
                f"`{normalized_inline_motion}` is not in motion_catalog or motion_map. "
                f"catalog keys: {motion_catalog_keys}, map keys: {motion_map_keys}"
            )

    if not resolved_motions:
        resolved_motions = resolve_action_asset_list(
            motion_map,
            decision.base_expression,
            allow_fallback=False,
        )
        if resolved_motions:
            motion_source = "base_expression_map"

    resolved_expressions = []
    if not resolved_motions:
        resolved_expressions = resolve_action_asset_list(
            emotion_map,
            decision.base_expression,
            allow_fallback=False,
        )
        if not resolved_expressions:
            resolved_expressions = resolve_action_asset_list(
                emotion_map,
                decision.base_expression,
            )

    decision_payload = decision.to_payload()
    if normalized_inline_motion:
        decision_payload["requested_motion_id"] = normalized_inline_motion
    if motion_source in {"inline_motion_id", "inline_motion_catalog_id"}:
        decision_payload["motion_id"] = normalized_inline_motion
    elif motion_source == "base_expression_map" and resolved_motions:
        decision_payload["motion_id"] = decision.base_expression
    if motion_source:
        decision_payload["motion_source"] = motion_source

    if resolved_motions:
        actions: dict[str, Any] = {
            "motions": resolved_motions,
            "expression_decision": decision_payload,
        }
    else:
        resolved_expression = resolved_expressions[0] if resolved_expressions else "neutral"
        actions = {
            "expressions": [resolved_expression],
            "expression_decision": decision_payload,
        }
    if motion_error:
        actions["motion_decision_error"] = motion_error
    logger.info(
        "[Live2DExpr] decision source=%s motion_source=%s motion_asset=%s base_expression=%s semantic_expression=%s",
        decision_source,
        motion_source or "<none>",
        resolved_motions[0] if resolved_motions else "<none>",
        decision.base_expression,
        decision.semantic_expression,
    )
    return actions


def normalize_action_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def normalize_action_asset_list(value: Any) -> list[str]:
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


def collect_action_map_keys(*asset_maps: Any) -> list[str]:
    ordered_keys: list[str] = []
    seen_keys: set[str] = set()

    for asset_map in asset_maps:
        if not isinstance(asset_map, dict):
            continue
        for raw_key in asset_map.keys():
            normalized_key = normalize_action_key(raw_key)
            if not normalized_key or normalized_key in seen_keys:
                continue
            seen_keys.add(normalized_key)
            ordered_keys.append(normalized_key)

    return ordered_keys


def resolve_action_asset_list(
    asset_map: Any,
    decision_key: str,
    *,
    allow_fallback: bool = True,
) -> list[str]:
    if not isinstance(asset_map, dict) or not asset_map:
        return []

    normalized_key = normalize_action_key(decision_key)
    if normalized_key:
        for key, value in asset_map.items():
            if normalize_action_key(key) == normalized_key:
                return normalize_action_asset_list(value)

    if not allow_fallback:
        return []

    for value in asset_map.values():
        normalized_assets = normalize_action_asset_list(value)
        if normalized_assets:
            return normalized_assets

    return []
