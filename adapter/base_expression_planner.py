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


SYSTEM_PROMPT = """你是一个 Live2D 基础表情规划器。

你的任务是根据：
- 人格设定
- 最近对话上下文
- 当前用户输入
- 当前回复文本

判断当前回复最合适的语义情绪 semantic_expression，
并从 emotion_map_keys 中选择一个最接近、最可执行的 base_expression。

要求：
1. semantic_expression 表示语义层情绪，可以不受 emotion_map_keys 限制。
2. base_expression 必须严格来自 emotion_map_keys。
3. 输出严格 JSON。
4. 不要输出参数，不要输出模板，不要输出其他说明文字。
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
    payload = {
        "persona": {
            "name": (persona or {}).get("name", "default"),
            "summary": _build_persona_summary(persona or {}),
        },
        "recent_context": chatbuffer[-10:],
        "user_input": user_input,
        "reply_text": reply_text,
        "emotion_map_keys": emotion_map_keys,
        "output_schema_hint": {
            "semantic_expression": "embarrassed",
            "base_expression": emotion_map_keys[0] if emotion_map_keys else "neutral",
            "reason": "简要说明为什么这句回复适合该基础表情",
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
    semantic = _guess_semantic_expression(reply_text)
    base_expression = _map_semantic_to_base_expression(semantic, emotion_map_keys)
    return BaseExpressionDecision(
        semantic_expression=semantic,
        base_expression=base_expression,
        reason="fallback by local semantic mapping",
    )


def _guess_semantic_expression(reply_text: str) -> str:
    text = (reply_text or "").strip().lower()
    if not text:
        return "neutral"
    rules = [
        ("angry", ("angry", "mad", "annoyed", "生气", "烦", "恼火")),
        ("surprised", ("wow", "surprise", "unexpected", "哇", "惊讶", "没想到")),
        ("thinking", ("think", "consider", "让我想想", "思考")),
        ("embarrassed", ("不好意思", "害羞", "嘴硬", "别问", "才不是", "才没有")),
        ("happy", ("great", "awesome", "开心", "高兴", "喜欢", "不错")),
        ("tired", ("sorry", "sad", "抱歉", "难过", "遗憾", "累")),
    ]
    for semantic, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return semantic
    return "neutral"


def _map_semantic_to_base_expression(semantic_expression: str, emotion_map_keys: list[str]) -> str:
    aliases = {
        "neutral": ["neutral"],
        "happy": ["happy", "joy", "smirk"],
        "angry": ["angry", "anger", "disgust"],
        "surprised": ["surprised", "surprise"],
        "thinking": ["thinking", "confused", "smirk"],
        "embarrassed": ["embarrassed", "smirk", "confused", "sadness"],
        "tired": ["tired", "sadness", "fear"],
    }
    candidates = aliases.get(semantic_expression, []) + ["neutral"]
    for candidate in candidates:
        if candidate in emotion_map_keys:
            return candidate
    return emotion_map_keys[0]


def _build_persona_summary(persona: dict[str, Any]) -> str:
    name = persona.get("name", "default")
    prompt = str(persona.get("prompt", "")).strip()
    begin_dialogs = persona.get("begin_dialogs", [])

    parts = [f"name={name}"]
    if prompt:
        parts.append(f"prompt={prompt[:300]}")
    if isinstance(begin_dialogs, list) and begin_dialogs:
        parts.append(f"begin_dialogs_count={len(begin_dialogs)}")
    return " | ".join(parts)


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
