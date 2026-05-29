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
    "HOP_WEIGHT_TOLERANCE": {
        "type": "int",
        "min": 0,
        "max": 500,
        "default": 1,
        "label": "Hop tolerance (g)",
    },
    "DEBUG": {
        "type": "bool",
        "default": False,
        "label": "Debug mode",
    },
    "UPDATE_BRANCH": {
        "type": "str",
        "max_len": 64,
        "default": "main",
        "label": "Update branch",
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
    "BREWING_SOFTWARE",
    "BREWFATHER_USER_ID",
    "BREWFATHER_API_KEY",
    "GRAIN_WEIGHT_TOLERANCE",
    "HOP_WEIGHT_TOLERANCE",
    "DEBUG",
    "UPDATE_BRANCH",
]
