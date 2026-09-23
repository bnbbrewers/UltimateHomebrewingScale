"""
API factory to instantiate API connectors once at boot.
"""

import runtime_debug

_BREWING_SOFTWARE = runtime_debug.setting("BREWING_SOFTWARE", "brewfather")


class ApiFactory:
    def __init__(self, wifi_device=None):
        self._wifi_device = wifi_device
        runtime_debug.collect()
        runtime_debug.snapshot("api_factory.init.start", collect=True)
        self._connectors = {}
        self._builders = {
            "brewing": self._build_brewing,
        }
        runtime_debug.collect()
        runtime_debug.snapshot("api_factory.init.done", collect=True)

    def _build_brewing(self):
        if _BREWING_SOFTWARE != "brewfather":
            return None
        runtime_debug.collect()
        runtime_debug.snapshot("api_factory.brewfather.before_import", collect=True)
        from api.brewfather_api import BrewfatherAPI

        connector = BrewfatherAPI(wifi_device=self._wifi_device)
        runtime_debug.collect()
        runtime_debug.snapshot("api_factory.brewfather.created", collect=True)
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
