"""
Devices module for Ultimate Homebrewing Scale
Provides hardware abstraction layers for sensors and actuators
"""

from .scale import CalibratedScale
from .wifi import WifiDevice
from .button import ButtonDevice
from .rotary import RotaryDevice
from .speaker import SpeakerDevice, get_speaker

__all__ = [
    "CalibratedScale",
    "WifiDevice",
    "ButtonDevice",
    "RotaryDevice",
    "SpeakerDevice",
    "get_speaker",
]
