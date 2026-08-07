"""
Singleton hardware manager for one-time hardware initialization.
"""

import gc

import M5
from M5 import *

from devices.scale import CalibratedScale
from devices.wifi import WifiDevice
from devices.button import ButtonDevice
from devices.rotary import RotaryDevice

try:
    import config
    _DEBUG = getattr(config, "DEBUG", False)
except Exception:
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
        _debug_snapshot(tag, enabled=True, collect=collect)


class HardwareManager:
    _instance = None

    def __init__(self):
        _collect_runtime()
        _mem_snapshot("hardware.init.start", enabled=_DEBUG, collect=True)
        self._relay = None
        self._relay_loaded = False
        self.button = ButtonDevice(M5.BtnA, button_id="A")
        _collect_runtime()
        _mem_snapshot("hardware.button", enabled=_DEBUG, collect=True)

        self.rotary = RotaryDevice()
        if self.rotary:
            self.rotary.reset()
        else:
            self.rotary = None
        _collect_runtime()
        _mem_snapshot("hardware.rotary", enabled=_DEBUG, collect=True)

        self.scale = None
        try:
            self.scale = CalibratedScale()
        except Exception:
            self.scale = None
        _collect_runtime()
        _mem_snapshot("hardware.scale", enabled=_DEBUG, collect=True)

        self.wifi = WifiDevice(debug=_DEBUG)
        _collect_runtime()
        _mem_snapshot("hardware.wifi", enabled=_DEBUG, collect=True)

    @property
    def relay(self):
        if not self._relay_loaded:
            self._relay_loaded = True
            try:
                from devices.relay import RelayDevice

                self._relay = RelayDevice()
                _collect_runtime()
                _mem_snapshot("hardware.relay", enabled=_DEBUG, collect=True)
            except Exception as e:
                self._relay = None
                _collect_runtime()
                _mem_snapshot("hardware.relay.failed", enabled=_DEBUG, collect=True)
                if _DEBUG:
                    try:
                        print("[Hardware] relay init failed: {}".format(e))
                    except Exception:
                        pass
        return self._relay

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = HardwareManager()
        return cls._instance

    def tick(self):
        self.button.tick()
        self.wifi.tick()
