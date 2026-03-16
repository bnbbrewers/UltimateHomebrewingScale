"""
Devices module for Ultimate Homebrewing Scale
Provides hardware abstraction layers for sensors and actuators
"""

from .scale import CalibratedScale
from .wifi import WifiDevice

__all__ = ["CalibratedScale", "WifiDevice"]
