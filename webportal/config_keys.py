"""Editable config schema for web portal."""

EDITABLE_KEYS = {
    "LANGUAGE": {
        "type": "enum",
        "choices": ["fr", "en"],
        "default": "en",
        "label": "Language",
    },
    "GRAIN_WEIGHT_TOLERANCE": {
        "type": "int",
        "min": 0,
        "max": 500,
        "default": 10,
        "label": "Grain tolerance (g)",
    },
    "DEBUG": {
        "type": "bool",
        "default": False,
        "label": "Debug mode",
    },
    "WIFI_SSID": {
        "type": "str",
        "max_len": 64,
        "default": "",
        "label": "Wi-Fi SSID",
    },
    "WIFI_PASSWORD": {
        "type": "str",
        "max_len": 64,
        "default": "",
        "label": "Wi-Fi password",
    },
    "BREWFATHER_USER_ID": {
        "type": "str",
        "max_len": 96,
        "default": "",
        "label": "Brewfather user id",
    },
    "BREWFATHER_API_KEY": {
        "type": "str",
        "max_len": 128,
        "default": "",
        "label": "Brewfather API key",
    },
    "BREWING_SOFTWARE": {
        "type": "enum",
        "choices": ["brewfather"],
        "default": "brewfather",
        "label": "Brewing software",
    },
}

EDITABLE_ORDER = [
    "LANGUAGE",
    "WIFI_SSID",
    "WIFI_PASSWORD",
    "BREWFATHER_USER_ID",
    "BREWFATHER_API_KEY",
    "GRAIN_WEIGHT_TOLERANCE",
    "DEBUG",
    "BREWING_SOFTWARE",
]
