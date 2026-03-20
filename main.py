from pathlib import Path
import logging

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star

from .adapter.inline_expression import (
    LIVE2D_BASE_EXPRESSION_EXTRA_KEY,
    build_base_expression_hook_prompt,
    collect_available_base_expressions,
    extract_inline_base_expression,
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

        plugin_config = self.config if self.config is not None else {}
        selected_model_name = ""
        if hasattr(plugin_config, "get"):
            selected_model_name = str(plugin_config.get("live2d_model_name", "") or "")

        live2ds_dir = Path(__file__).resolve().parent / "live2ds"
        base_expressions = collect_available_base_expressions(
            live2ds_dir=live2ds_dir,
            selected_model_name=selected_model_name,
        )
        if not base_expressions:
            return

        hook_prompt = build_base_expression_hook_prompt(base_expressions)
        if not hook_prompt:
            return

        if req.system_prompt:
            req.system_prompt = req.system_prompt.rstrip() + hook_prompt
        else:
            req.system_prompt = hook_prompt.lstrip()
        logger.debug(
            "[Live2DExpr] hook request injected model=%s func_tool=%s",
            selected_model_name or "<default>",
            req.func_tool is not None,
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

        plugin_config = self.config if self.config is not None else {}
        selected_model_name = ""
        if hasattr(plugin_config, "get"):
            selected_model_name = str(plugin_config.get("live2d_model_name", "") or "")

        live2ds_dir = Path(__file__).resolve().parent / "live2ds"
        base_expressions = collect_available_base_expressions(
            live2ds_dir=live2ds_dir,
            selected_model_name=selected_model_name,
        )
        if not base_expressions:
            return

        extracted_expression, cleaned_text = extract_inline_base_expression(
            resp.completion_text or "",
            allowed_base_expressions=base_expressions,
        )
        if not extracted_expression:
            logger.debug("[Live2DExpr] hook response extracted nothing")
            return

        logger.info(
            "[Live2DExpr] hook response extracted base_expression=%s",
            extracted_expression,
        )
        event.set_extra(LIVE2D_BASE_EXPRESSION_EXTRA_KEY, extracted_expression)
        resp.completion_text = cleaned_text


def _configure_noisy_loggers() -> None:
    for logger_name in (
        "pyffmpeg",
        "pyffmpeg.FFmpeg",
        "pyffmpeg.misc.Paths",
    ):
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)
