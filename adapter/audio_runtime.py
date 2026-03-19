from __future__ import annotations

from contextlib import contextmanager
import sys
from pathlib import Path
from typing import Any

from astrbot.api import logger


@contextmanager
def temporary_olv_import_path(olv_dir: Path):
    inserted_paths: list[str] = []
    candidate_paths = [str(olv_dir), str(olv_dir / "src")]

    for path_str in candidate_paths:
        if path_str in sys.path:
            continue
        sys.path.insert(0, path_str)
        inserted_paths.append(path_str)

    try:
        yield
    finally:
        for path_str in inserted_paths:
            try:
                sys.path.remove(path_str)
            except ValueError:
                continue


def create_vad_engine(
    olv_dir: Path,
    engine_type: str,
    kwargs: dict[str, Any],
):
    if not engine_type:
        return None

    with temporary_olv_import_path(olv_dir):
        from src.open_llm_vtuber.vad.vad_factory import VADFactory

    logger.info(f"Initializing OLV VAD: {engine_type}")
    return VADFactory.get_vad_engine(engine_type, **kwargs)
