"""
Applications module for Ultimate Homebrewing Scale

All applications inherit from BaseApp and follow the same pattern:
- __init__(i18n=None): Initialize app with optional i18n
- create_ui(): Create LVGL UI elements
- update(): Update app state (called every frame)
- check_return_to_launcher(): Check if user wants to exit
- run(): Main loop (inherited from BaseApp)
- cleanup(): Clean up resources (inherited from BaseApp)
"""

from .base_app import BaseApp
from . import scale
from . import grain_assistant
from . import hop_assistant
from . import keg_filler
from . import settings

__all__ = [
    'BaseApp',
    'scale',
    'grain_assistant',
    'hop_assistant',
    'keg_filler',
    'settings',
]
