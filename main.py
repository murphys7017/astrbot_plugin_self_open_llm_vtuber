from pathlib import Path
import logging

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star

from .adapter.model_info import DEFAULT_LIVE2D_MODEL_NAME
from .adapter.inline_expression import (
    LIVE2D_BASE_EXPRESSION_EXTRA_KEY,
    LIVE2D_MOTION_ID_EXTRA_KEY,
    build_inline_anim_hook_prompt,
    collect_available_base_expressions,
    collect_available_motion_ids,
    collect_motion_catalog_descriptions,
    extract_inline_anim_decision,
    select_motion_candidates,
)


class MyPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        from .adapter.plugin_runtime import set_plugin_config, set_plugin_context

        self.context = context
        self.config = config if config is not None else {}
        _configure_noisy_loggers()
        set_plugin_context(context)
        set_plugin_config(self.config)
        # Import solely for side effect: the class decorator registers the adapter.
        from .platform_adapter import OLVPetPlatformAdapter  # noqa: F401

    @filter.on_llm_request()
    async def inject_live2d_base_expression_tagging(
        self,
        event: AstrMessageEvent,
        req: ProviderRequest,
    ) -> None:
        if event.get_platform_id() != "olv_pet_adapter":
            return

        plugin_config = _load_latest_plugin_config(self.config)
        selected_model_name = _plugin_config_value(
            plugin_config,
            "live2d_model_name",
            DEFAULT_LIVE2D_MODEL_NAME,
        )

        live2ds_dir = Path(__file__).resolve().parent / "live2ds"
        base_expressions = collect_available_base_expressions(
            live2ds_dir=live2ds_dir,
            selected_model_name=selected_model_name,
        )
        motion_ids = collect_available_motion_ids(
            live2ds_dir=live2ds_dir,
            selected_model_name=selected_model_name,
        )
        if not base_expressions and not motion_ids:
            return

        motion_candidate_limit = 8
        try:
            motion_candidate_limit = int(
                _plugin_config_value(plugin_config, "motion_candidate_limit", 8) or 8
            )
        except Exception:
            motion_candidate_limit = 8
        motion_candidates = select_motion_candidates(
            motion_ids,
            max_candidates=max(motion_candidate_limit, 0),
        )
        motion_descriptions = collect_motion_catalog_descriptions(
            live2ds_dir=live2ds_dir,
            selected_model_name=selected_model_name,
        )

        hook_prompt = build_inline_anim_hook_prompt(
            motion_candidates=motion_candidates,
            base_expressions=base_expressions,
            motion_descriptions=motion_descriptions,
        )
        if not hook_prompt:
            return

        if req.system_prompt:
            req.system_prompt = req.system_prompt.rstrip() + hook_prompt
        else:
            req.system_prompt = hook_prompt.lstrip()
        logger.debug(
            "[Live2DExpr] hook request injected model=%s func_tool=%s "
            "motion_candidates=%s candidate_preview=%s catalog_descriptions=%s catalog_preview=%s",
            selected_model_name or "<default>",
            req.func_tool is not None,
            len(motion_candidates),
            ", ".join(motion_candidates[:8]) if motion_candidates else "<none>",
            len(motion_descriptions),
            ", ".join(list(motion_descriptions.keys())[:8])
            if motion_descriptions
            else "<none>",
        )

    @filter.on_llm_response()
    async def extract_live2d_base_expression_tag(
        self,
        event: AstrMessageEvent,
        resp: LLMResponse,
    ) -> None:
        if event.get_platform_id() != "olv_pet_adapter":
            return
        if resp.is_chunk:
            return

        plugin_config = _load_latest_plugin_config(self.config)
        selected_model_name = _plugin_config_value(
            plugin_config,
            "live2d_model_name",
            DEFAULT_LIVE2D_MODEL_NAME,
        )

        live2ds_dir = Path(__file__).resolve().parent / "live2ds"
        base_expressions = collect_available_base_expressions(
            live2ds_dir=live2ds_dir,
            selected_model_name=selected_model_name,
        )
        motion_ids = collect_available_motion_ids(
            live2ds_dir=live2ds_dir,
            selected_model_name=selected_model_name,
        )
        if not base_expressions and not motion_ids:
            return

        decision, cleaned_text = extract_inline_anim_decision(
            resp.completion_text or "",
            allowed_motion_ids=motion_ids,
            allowed_base_expressions=base_expressions,
        )
        if not decision:
            logger.debug("[Live2DExpr] hook response extracted nothing (anim/base)")
            return

        extracted_motion_id = decision.get("motion_id")
        extracted_expression = decision.get("base_expression")
        if extracted_motion_id:
            event.set_extra(LIVE2D_MOTION_ID_EXTRA_KEY, extracted_motion_id)
        if extracted_expression:
            event.set_extra(LIVE2D_BASE_EXPRESSION_EXTRA_KEY, extracted_expression)

        logger.info(
            "[Live2DExpr] hook response extracted model=%s motion_id=%s base_expression=%s",
            selected_model_name or "<default>",
            extracted_motion_id or "<none>",
            extracted_expression or "<none>",
        )
        resp.completion_text = cleaned_text


def _configure_noisy_loggers() -> None:
    for logger_name in (
        "pyffmpeg",
        "pyffmpeg.FFmpeg",
        "pyffmpeg.misc.Paths",
    ):
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)


def _load_latest_plugin_config(fallback_config: dict | None = None):
    from .adapter.plugin_runtime import get_plugin_config

    latest = get_plugin_config()
    if latest is not None:
        return latest
    return fallback_config if fallback_config is not None else {}


def _plugin_config_value(config: dict | None, key: str, default):
    if config is None:
        return default
    if hasattr(config, "get"):
        value = config.get(key, default)
        return default if value is None else value
    return default
