"""
API factory to instantiate API connectors once at boot.
"""

try:
    import config
    _BREWING_SOFTWARE = getattr(config, "BREWING_SOFTWARE", "brewfather")
except Exception:
    _BREWING_SOFTWARE = "brewfather"


class ApiFactory:
    def __init__(self):
        self._connectors = {}
        self._build()

    def _build(self):
        if _BREWING_SOFTWARE == "brewfather":
            from api.brewfather_api import BrewfatherAPI

            self._connectors["brewing"] = BrewfatherAPI()
        else:
            self._connectors["brewing"] = None

    def get(self, name):
        return self._connectors.get(name)

    def as_dict(self):
        return self._connectors
