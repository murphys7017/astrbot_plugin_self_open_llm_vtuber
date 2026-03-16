from astrbot.api.star import Context, Star

class MyPlugin(Star):
    def __init__(self, context: Context):
        from .platform_adapter import OLVPetPlatformAdapter  # noqa: F401
