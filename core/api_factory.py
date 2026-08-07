"""
API factory to instantiate API connectors once at boot.
"""

import gc

try:
    import config
    _BREWING_SOFTWARE = getattr(config, "BREWING_SOFTWARE", "brewfather")
    _DEBUG = getattr(config, "DEBUG", False)
except Exception:
    _BREWING_SOFTWARE = "brewfather"
    _DEBUG = False

if _DEBUG:
    try:
        from memory_debug import snapshot as _debug_snapshot
    except Exception:
        _debug_snapshot = None
else:
    _debug_snapshot = None


def _collect_runtime(cycles=1):
    for _ in range(max(1, cycles)):
        gc.collect()


def _mem_snapshot(tag, enabled=True, collect=False):
    if enabled and _debug_snapshot:
        _debug_snapshot(tag, enabled=True, collect=False)


class ApiFactory:
    def __init__(self):
        _collect_runtime()
        _mem_snapshot("api_factory.init.start", enabled=_DEBUG, collect=True)
        self._connectors = {}
        self._builders = {
            "brewing": self._build_brewing,
        }
        _collect_runtime()
        _mem_snapshot("api_factory.init.done", enabled=_DEBUG, collect=True)

    def _build_brewing(self):
        if _BREWING_SOFTWARE != "brewfather":
            return None
        _collect_runtime()
        _mem_snapshot("api_factory.brewfather.before_import", enabled=_DEBUG, collect=True)
        from api.brewfather_api import BrewfatherAPI

        connector = BrewfatherAPI()
        _collect_runtime()
        _mem_snapshot("api_factory.brewfather.created", enabled=_DEBUG, collect=True)
        return connector

    def get(self, name):
        if name in self._connectors:
            return self._connectors[name]
        builder = self._builders.get(name)
        if builder is None:
            return None
        connector = builder()
        self._connectors[name] = connector
        return connector

    def as_dict(self):
        # Existing applications only depend on the mapping's get() contract.
        # Returning the factory keeps connector construction lazy.
        return self

    def __getitem__(self, name):
        value = self.get(name)
        if value is None:
            raise KeyError(name)
        return value
