from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from astrbot import logger


def ensure_olv_import_path(olv_dir: Path) -> None:
    for path in (olv_dir, olv_dir / "src"):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def create_vad_engine(
    olv_dir: Path,
    engine_type: str,
    kwargs: dict[str, Any],
):
    if not engine_type:
        return None

    ensure_olv_import_path(olv_dir)
    from src.open_llm_vtuber.vad.vad_factory import VADFactory

    logger.info(f"Initializing OLV VAD: {engine_type}")
    return VADFactory.get_vad_engine(engine_type, **kwargs)
