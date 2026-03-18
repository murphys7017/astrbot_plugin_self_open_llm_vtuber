from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any

from astrbot.api.provider import Provider


@dataclass(frozen=True)
class BaseExpressionDecision:
    semantic_expression: str
    base_expression: str
    reason: str = ""

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


class BaseExpressionPlanningError(ValueError):
    pass


SYSTEM_PROMPT = """你是一个 Live2D 表情规划器。

任务：
根据输入信息，判断语义情绪 semantic_expression，
并从 emotion_map_keys 中选择 base_expression。

要求：
1. base_expression 必须严格来自 emotion_map_keys。
2. 如果存在明显情绪，不要选择 neutral。
3. 输出必须是 JSON。
4. 格式如下：

{
  "semantic_expression": string,
  "base_expression": string
}

5. 不要输出任何额外内容。
"""


async def plan_base_expression(
    provider: Provider | None,
    *,
    persona: dict[str, Any] | None,
    chatbuffer: list[dict[str, str]],
    user_input: str,
    reply_text: str,
    emotion_map_keys: list[str],
) -> BaseExpressionDecision:
    emotion_map_keys = [item for item in emotion_map_keys if isinstance(item, str) and item]
    if not emotion_map_keys:
        return BaseExpressionDecision(
            semantic_expression="neutral",
            base_expression="neutral",
            reason="emotion_map_keys is empty",
        )

    if provider is None:
        return build_fallback_base_expression_decision(reply_text, emotion_map_keys)

    prompt = build_base_expression_prompt(
        persona=persona,
        chatbuffer=chatbuffer,
        user_input=user_input,
        reply_text=reply_text,
        emotion_map_keys=emotion_map_keys,
    )
    response = await provider.text_chat(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
    )
    completion_text = (response.completion_text or "").strip()
    if not completion_text:
        raise BaseExpressionPlanningError("Base expression planner returned empty completion_text.")
    return validate_base_expression_decision(completion_text, emotion_map_keys)


def build_base_expression_prompt(
    *,
    persona: dict[str, Any] | None,
    chatbuffer: list[dict[str, str]],
    user_input: str,
    reply_text: str,
    emotion_map_keys: list[str],
) -> str:
    persona_payload = persona or {}
    payload = {
        "persona": {
            "name": persona_payload.get("name", "default"),
            "prompt": persona_payload.get("prompt", ""),
            "begin_dialogs": persona_payload.get("begin_dialogs", []),
            "custom_error_message": persona_payload.get("custom_error_message"),
        },
        "recent_context": chatbuffer[-10:],
        "user_input": user_input,
        "reply_text": reply_text,
        "emotion_map_keys": emotion_map_keys,
        "output_schema_hint": {
            "semantic_expression": "string",
            "base_expression": "string, must be one of emotion_map_keys",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def validate_base_expression_decision(
    raw_text: str,
    emotion_map_keys: list[str],
) -> BaseExpressionDecision:
    payload = _load_json_payload(raw_text)
    if not isinstance(payload, dict):
        raise BaseExpressionPlanningError("Planner output must be a JSON object.")

    semantic_expression = str(payload.get("semantic_expression", "")).strip()
    base_expression = str(payload.get("base_expression", "")).strip()
    reason = str(payload.get("reason", "")).strip()

    if not semantic_expression:
        raise BaseExpressionPlanningError("`semantic_expression` must be a non-empty string.")
    if base_expression not in emotion_map_keys:
        raise BaseExpressionPlanningError(
            f"`base_expression` value `{base_expression}` is not allowed. Allowed: {emotion_map_keys}"
        )

    return BaseExpressionDecision(
        semantic_expression=semantic_expression,
        base_expression=base_expression,
        reason=reason,
    )


def build_fallback_base_expression_decision(
    reply_text: str,
    emotion_map_keys: list[str],
) -> BaseExpressionDecision:
    del reply_text
    base_expression = "neutral" if "neutral" in emotion_map_keys else emotion_map_keys[0]
    return BaseExpressionDecision(
        semantic_expression="neutral",
        base_expression=base_expression,
        reason="fallback to neutral",
    )


def _load_json_payload(raw_text: str) -> Any:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)
