"""
Singleton hardware manager for one-time hardware initialization.
"""

import M5
from M5 import *

from devices.scale import CalibratedScale
from devices.wifi import WifiDevice
from devices.button import ButtonDevice
from devices.rotary import RotaryDevice
from devices.speaker import get_speaker

try:
    import config
    _DEBUG = getattr(config, "DEBUG", False)
except Exception:
    _DEBUG = False


class RelayDevice:
    """
    Safe relay abstraction.
    Defaults to software-only state when physical relay is unavailable.
    """

    def __init__(self):
        self._state = False

    def set_on(self):
        self._state = True

    def set_off(self):
        self._state = False

    def is_on(self):
        return self._state


class HardwareManager:
    _instance = None

    def __init__(self):
        self.button = ButtonDevice(M5.BtnA, button_id="A")

        self.rotary = RotaryDevice()
        if self.rotary:
            self.rotary.reset()
        else:
            self.rotary = None

        self.scale = None
        try:
            self.scale = CalibratedScale()
        except Exception:
            self.scale = None

        self.relay = RelayDevice()
        self.speaker = get_speaker()
        if self.speaker:
            self.speaker.begin()
        self.wifi = WifiDevice(debug=_DEBUG)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = HardwareManager()
        return cls._instance

    def tick(self):
        self.button.tick()
        self.wifi.tick()
