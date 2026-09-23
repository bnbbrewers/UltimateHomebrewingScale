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
import runtime_debug


class HardwareManager:
    _instance = None

    def __init__(self):
        runtime_debug.collect()
        runtime_debug.snapshot("hardware.init.start", collect=True)
        self._relay = None
        self._relay_loaded = False
        self.button = ButtonDevice(M5.BtnA, button_id="A")
        runtime_debug.collect()
        runtime_debug.snapshot("hardware.button", collect=True)

        self.rotary = RotaryDevice()
        if self.rotary:
            self.rotary.reset()
        else:
            self.rotary = None
        runtime_debug.collect()
        runtime_debug.snapshot("hardware.rotary", collect=True)

        self.scale = None
        try:
            self.scale = CalibratedScale()
        except Exception:
            self.scale = None
        runtime_debug.collect()
        runtime_debug.snapshot("hardware.scale", collect=True)

        self.wifi = WifiDevice(debug=runtime_debug.DEBUG)
        runtime_debug.collect()
        runtime_debug.snapshot("hardware.wifi", collect=True)

    @property
    def relay(self):
        if not self._relay_loaded:
            self._relay_loaded = True
            try:
                from devices.relay import RelayDevice

                self._relay = RelayDevice()
                runtime_debug.collect()
                runtime_debug.snapshot("hardware.relay", collect=True)
            except Exception as e:
                self._relay = None
                runtime_debug.collect()
                runtime_debug.snapshot("hardware.relay.failed", collect=True)
                runtime_debug.log("[Hardware] relay init failed: {}", e)
        return self._relay

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = HardwareManager()
        return cls._instance

    def tick(self):
        self.button.tick()
        self.wifi.tick()
