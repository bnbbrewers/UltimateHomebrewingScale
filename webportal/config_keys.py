"""Editable config schema for web portal."""

EDITABLE_KEYS = {
    'HOSTNAME': {'type': 'str', 'default': 'uhs-scale', 'label': 'Device hostname', 'max_len': 32},
    'SIMULATION_ENABLED': {'type': 'bool', 'default': False, 'label': 'Simulate scale (physical relay disabled)'},
    'SIMULATION_MODE': {'type': 'enum', 'default': 'ramp', 'label': 'Simulation mode', 'choices': ['ramp', 'fixed']},
    'SIMULATION_WEIGHT_G': {'type': 'int', 'default': 1000, 'label': 'Simulation target (g)', 'min': 0, 'max': 10000000},
    'SIMULATION_RATE_G_S': {'type': 'int', 'default': 100, 'label': 'Simulation speed (g/s)', 'min': 1, 'max': 10000},
    'SIMULATION_SEND_EVENTS': {'type': 'bool', 'default': False, 'label': 'Send simulated data to API (creates real history)'},

    "LANGUAGE": {
        "type": "enum",
        "choices": ["fr", "en"],
        "default": "en",
        "label": "Language",
    },
    # Display only: every stored value stays metric (see units.py).
    "UNITS": {
        "type": "enum",
        "choices": ["metric", "us", "imperial"],
        "default": "metric",
        "label": "Units",
    },
    "GRAIN_WEIGHT_TOLERANCE": {
        "type": "int",
        "min": 0,
        "max": 500,
        "default": 10,
        "label": "Grain tolerance",
    },
    "HOP_WEIGHT_TOLERANCE": {
        "type": "int",
        "min": 0,
        "max": 500,
        "default": 1,
        "label": "Hop tolerance",
    },
    "KEG_SPUNDING_VALVE_INERTIA_ML": {
        "type": "int",
        "min": 0,
        "max": 5000,
        "default": 200,
        "label": "Spunding valve inertia",
    },
    # Bounds mirror apps.keg_filler_app: the stall guard cannot be disabled.
    "KEG_FILL_STALL_TIMEOUT_S": {
        "type": "int",
        "min": 3,
        "max": 600,
        "default": 10,
        "label": "Fill stall safety (s)",
    },
    "STANDBY_TIMEOUT_MIN": {
        "type": "int",
        "min": 0,
        "max": 240,
        "default": 0,
        "label": "Standby after (min, 0 = off)",
    },
    # Virtual key: config_registry never writes a BATTERY line, it translates
    # this box into the presence of WATCHDOG_TIMEOUT_MS (see that module).
    # No timeout field is exposed: on battery the value is always 15000 ms.
    "BATTERY": {
        "type": "bool",
        "default": False,
        "label": "Battery powered",
    },
    "DEBUG": {
        "type": "bool",
        "default": False,
        "label": "Debug mode",
    },
    "UPDATE_CHANNEL": {
        "type": "enum",
        "choices": ["stable", "prerelease"],
        "default": "stable",
        "label": "Release channel",
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
    'HTTP_INTEGRATION_ENABLED': {'type': 'bool', 'default': False, 'label': 'Enable HTTP integration'},
    'HTTP_API_BASE_URL': {'type': 'str', 'default': '', 'label': 'HTTP API base URL', 'max_len': 512},
    'HTTP_WEBHOOK_URL': {'type': 'str', 'default': '', 'label': 'Webhook URL (optional)', 'max_len': 512},
    'HTTP_API_TOKEN': {'type': 'str', 'default': '', 'label': 'HTTP Bearer token', 'max_len': 512},
    'HTTP_LIVE_ENABLED': {'type': 'bool', 'default': False, 'label': 'Send live measurements'},
    'HTTP_MEASUREMENT_INTERVAL_MS': {'type': 'int', 'default': 1000, 'label': 'Live interval (ms, minimum 1000)', 'min': 1000, 'max': 3600000},
    "BREWING_SOFTWARE": {
        "type": "enum",
        "choices": ["brewfather", "generic_http"],
        "default": "brewfather",
        "label": "Brewing software",
    },
}

EDITABLE_ORDER = [
    'HOSTNAME',
    'SIMULATION_ENABLED',
    'SIMULATION_MODE',
    'SIMULATION_WEIGHT_G',
    'SIMULATION_RATE_G_S',
    'SIMULATION_SEND_EVENTS',

    "LANGUAGE",
    "UNITS",
    "WIFI_SSID",
    "WIFI_PASSWORD",
    "BREWING_SOFTWARE",
    'HTTP_INTEGRATION_ENABLED',
    'HTTP_API_BASE_URL',
    'HTTP_WEBHOOK_URL',
    'HTTP_API_TOKEN',
    'HTTP_LIVE_ENABLED',
    'HTTP_MEASUREMENT_INTERVAL_MS',

    "BREWFATHER_USER_ID",
    "BREWFATHER_API_KEY",
    "GRAIN_WEIGHT_TOLERANCE",
    "HOP_WEIGHT_TOLERANCE",
    "KEG_SPUNDING_VALVE_INERTIA_ML",
    "KEG_FILL_STALL_TIMEOUT_S",
    "STANDBY_TIMEOUT_MIN",
    "BATTERY",
    "DEBUG",
    "UPDATE_CHANNEL",
]
