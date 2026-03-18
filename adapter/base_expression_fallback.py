"""Rule-based fallback mapping for base expressions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExpressionDecision:
    """Expression mapping output used by payload construction."""

    template: str
    actions: dict[str, Any]


class RuleBasedExpressionMapper:
    """Very small keyword mapper for initial Live2D expression output."""

    def __init__(self) -> None:
        self._rules: list[tuple[str, tuple[str, ...]]] = [
            ("happy", ("!", "great", "awesome", "amazing", "太棒", "开心", "高兴")),
            ("happy", ("nice", "good", "glad", "happy", "不错", "喜欢", "开心")),
            ("tired", ("sorry", "sad", "unfortunately", "抱歉", "难过", "遗憾")),
            ("angry", ("angry", "mad", "annoyed", "生气", "烦", "恼火")),
            ("surprised", ("wow", "surprise", "unexpected", "哇", "惊讶", "没想到")),
            ("thinking", ("think", "consider", "let me see", "让我想想", "思考")),
        ]

    def decide(self, text: str) -> ExpressionDecision:
        """Map reply text to a stable template and actions payload."""
        normalized = (text or "").strip().lower()
        if not normalized:
            return self._neutral()

        for template, keywords in self._rules:
            if any(keyword in normalized for keyword in keywords):
                return ExpressionDecision(
                    template=template,
                    actions={"expressions": [template]},
                )
        return self._neutral()

    @staticmethod
    def _neutral() -> ExpressionDecision:
        return ExpressionDecision(
            template="neutral",
            actions={"expressions": ["neutral"]},
        )
