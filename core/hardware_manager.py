"""
Singleton hardware manager for one-time hardware initialization.
"""

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


class HardwareManager:
    _instance = None

    def __init__(self):
        self._relay = None
        self._relay_loaded = False
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

        self.wifi = WifiDevice(debug=_DEBUG)

    @property
    def relay(self):
        if not self._relay_loaded:
            self._relay_loaded = True
            try:
                from devices.relay import RelayDevice

                self._relay = RelayDevice()
            except Exception as e:
                self._relay = None
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
