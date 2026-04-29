"""
UI package marker.

Only expose screen ids here. Screen modules are imported directly by their
owners so calibration/settings-only UI code does not load during normal boot.
"""

from . import screen_ids

__all__ = ["screen_ids"]
