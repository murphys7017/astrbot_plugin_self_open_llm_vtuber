from __future__ import annotations

from typing import Any

from astrbot.api import logger

from .base_expression_planner import (
    BaseExpressionDecision,
    BaseExpressionPlanningError,
    build_fallback_base_expression_decision,
    plan_base_expression,
)
from .inline_expression import normalize_base_expression_key


async def build_expression_actions(
    *,
    runtime_state,
    chat_buffer,
    last_user_text: str,
    reply_text: str,
    inline_base_expression: str | None = None,
) -> dict[str, Any] | None:
    if not reply_text:
        return None

    emotion_map = runtime_state.model_info.get("emotionMap") or {}
    motion_map = runtime_state.model_info.get("motionMap") or {}
    action_map_keys = collect_action_map_keys(motion_map, emotion_map)
    normalized_inline_expression = normalize_base_expression_key(inline_base_expression)
    decision_source = "fallback"
    if normalized_inline_expression and normalized_inline_expression in action_map_keys:
        decision = BaseExpressionDecision(
            semantic_expression=normalized_inline_expression,
            base_expression=normalized_inline_expression,
            reason="inline llm tag",
        )
        planner_error = None
        decision_source = "inline_tag"
    else:
        decision = build_fallback_base_expression_decision(reply_text, action_map_keys)
        planner_error = None

    if (
        not normalized_inline_expression
        and runtime_state.selected_expression_provider is not None
    ):
        try:
            provider_id = runtime_state.selected_expression_provider.meta().id
        except Exception:
            provider_id = "<unknown>"
        logger.debug("Planning base expression with provider: %s", provider_id)
        try:
            decision = await plan_base_expression(
                runtime_state.selected_expression_provider,
                persona=runtime_state.default_persona,
                chatbuffer=chat_buffer.to_list(),
                user_input=last_user_text,
                reply_text=reply_text,
                emotion_map_keys=action_map_keys,
            )
            decision_source = "expression_provider"
        except BaseExpressionPlanningError as exc:
            planner_error = str(exc)
            logger.warning(
                "Base expression planner validation failed, fallback to neutral: %s",
                exc,
            )
        except Exception as exc:
            planner_error = str(exc)
            logger.warning("Base expression planner failed, fallback to neutral: %s", exc)

    resolved_motions = resolve_action_asset_list(
        motion_map,
        decision.base_expression,
        allow_fallback=False,
    )
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

    if resolved_motions:
        actions: dict[str, Any] = {
            "motions": resolved_motions,
            "expression_decision": decision.to_payload(),
        }
    else:
        resolved_expression = resolved_expressions[0] if resolved_expressions else "neutral"
        actions = {
            "expressions": [resolved_expression],
            "expression_decision": decision.to_payload(),
        }
    if planner_error:
        actions["expression_decision_error"] = planner_error
    logger.info(
        "[Live2DExpr] decision source=%s base_expression=%s semantic_expression=%s",
        decision_source,
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
