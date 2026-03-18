from __future__ import annotations

from typing import Any

_plugin_context: Any = None
_plugin_config: Any = None


def set_plugin_context(context: Any) -> None:
    global _plugin_context
    _plugin_context = context


def get_plugin_context() -> Any:
    return _plugin_context


def set_plugin_config(config: Any) -> None:
    global _plugin_config
    _plugin_config = config


def get_plugin_config() -> Any:
    return _plugin_config
