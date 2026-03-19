from __future__ import annotations

from copy import deepcopy
import threading
from typing import Any

_state_lock = threading.RLock()
_plugin_context: Any = None
_plugin_config: Any = None


def set_plugin_context(context: Any) -> None:
    global _plugin_context
    with _state_lock:
        _plugin_context = context


def get_plugin_context() -> Any:
    with _state_lock:
        return _plugin_context


def set_plugin_config(config: Any) -> None:
    global _plugin_config
    with _state_lock:
        _plugin_config = deepcopy(config)


def get_plugin_config() -> Any:
    with _state_lock:
        return deepcopy(_plugin_config)
