from .builtin import BUILTIN_PLUGINS
from .sdk import FiscalPlugin


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins = dict(BUILTIN_PLUGINS)

    def get(self, key: str) -> FiscalPlugin:
        try:
            return self._plugins[key]
        except KeyError as exc:
            raise LookupError(f"Plugin não registrado: {key}") from exc

    def all(self) -> list[FiscalPlugin]:
        return list(self._plugins.values())


registry = PluginRegistry()
