from astrbot.api.star import Context, Star


class MyPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context, config)
        from .adapter.plugin_runtime import set_plugin_config, set_plugin_context

        set_plugin_context(context)
        set_plugin_config(config if config is not None else {})
        # Import solely for side effect: the class decorator registers the adapter.
        from .platform_adapter import OLVPetPlatformAdapter  # noqa: F401
