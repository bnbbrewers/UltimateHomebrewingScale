"""
Devices module for Ultimate Homebrewing Scale
Provides hardware abstraction layers for sensors and actuators
"""

from .scale import CalibratedScale

__all__ = ['CalibratedScale']
