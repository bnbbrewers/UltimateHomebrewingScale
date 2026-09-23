"""
Launcher app controller (business logic only).
"""

import app_registry
import runtime_debug

from .base_app import BaseApp
from ui import screen_ids

# Built from the registry so the wheel cannot list an app the manager cannot
# open, or show a colour the loading screen does not share.
LAUNCHER_ITEMS = app_registry.launcher_items()


class LauncherApp(BaseApp):
    APP_ID = "launcher"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = None
        self._rotary = self.hardware.rotary
        self._items = LAUNCHER_ITEMS
        self._selected = 0

    def on_exit(self):
        super().on_exit()
        self._screen = None

    def on_enter(self):
        super().on_enter()
        self._screen = self.screen_manager.get(screen_ids.LAUNCHER)
        runtime_debug.log("[MEM] launcher.on_enter free={}", runtime_debug.mem_free())
        self.screen_manager.show(screen_ids.LAUNCHER)
        self._screen.set_items(self._items)
        self._selected = 0
        self._screen.set_selected_index(self._selected)
        if self._rotary:
            self._rotary.reset()

    def tick(self):
        if self._rotary:
            delta = self._rotary.consume_delta()
            if delta:
                self._screen.handle_rotary_delta(delta)
                self._selected = self._screen.get_selected_index()
        self._screen.animate_indicator()

        if self.hardware.button.was_short_pressed():
            if not self._items:
                return None
            return self._items[self._selected].get("module")
        return None
