"""
Launcher app controller (business logic only).
"""

import app_registry
import runtime_debug
import ticks

from .base_app import BaseApp
from ui import screen_ids
from updater import update_notice

# Built from the registry so the wheel cannot list an app the manager cannot
# open, or show a colour the loading screen does not share.
LAUNCHER_ITEMS = app_registry.launcher_items()

UPDATE_ICON = "/flash/assets/icons/Update.png"
# LV_SYMBOL_RIGHT: the built-in Montserrat fonts carry LVGL's symbols but no "→".
_ARROW = ""


class LauncherApp(BaseApp):
    APP_ID = "launcher"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = None
        self._rotary = self.hardware.rotary
        self._items = LAUNCHER_ITEMS
        self._selected = 0
        self._shown_notice = None
        self._last_input_ms = 0

    def on_exit(self):
        super().on_exit()
        self._screen = None

    def on_enter(self):
        super().on_enter()
        self._screen = self.screen_manager.get(screen_ids.LAUNCHER)
        runtime_debug.log("[MEM] launcher.on_enter free={}", runtime_debug.mem_free())
        self.screen_manager.show(screen_ids.LAUNCHER)
        self._shown_notice = update_notice.available()
        self._items = self._build_items(self._shown_notice)
        self._screen.set_items(self._items)
        self._selected = 0
        self._screen.set_selected_index(self._selected)
        self._last_input_ms = ticks.ticks_ms()
        if self._rotary:
            self._rotary.reset()

    def tick(self):
        # Reported here only: an app in use (a weighing, a keg fill) is never
        # interrupted, the problem waits for the operator to come back.
        wifi = getattr(self.hardware, "wifi", None)
        if wifi is not None and wifi.connection_failed():
            return app_registry.WIFI_PROBLEM
        now = ticks.ticks_ms()
        touched = False
        if self._rotary:
            delta = self._rotary.consume_delta()
            if delta:
                touched = True
                self._screen.handle_rotary_delta(delta)
                self._selected = self._screen.get_selected_index()
        self._screen.animate_indicator()

        if self.hardware.button.was_short_pressed():
            if not self._items:
                return None
            return self._items[self._selected].get("module")

        if touched:
            self._last_input_ms = now
        else:
            # Blocks for the length of one HTTPS call, once per boot, and
            # only after the operator left the wheel alone for a while.
            update_notice.tick(wifi, ticks.ticks_diff(now, self._last_input_ms))
            self._show_update_entry_if_new()
        return None

    def _show_update_entry_if_new(self):
        notice = update_notice.available()
        if notice is self._shown_notice:
            return
        self._shown_notice = notice
        self._items = self._build_items(notice)
        self._screen.set_items(self._items)
        self._selected = self._screen.get_selected_index()

    def _build_items(self, notice):
        if notice is None:
            return LAUNCHER_ITEMS
        local, remote = notice
        title = self.i18n.t("launcher.update") if self.i18n else "UPDATE"
        return LAUNCHER_ITEMS + [{
            "label": "UPDATE",
            "i18n": "launcher.update",
            "icon": UPDATE_ICON,
            "module": app_registry.UPDATE_PROMPT,
            "color": app_registry.color(app_registry.UPDATE_PROMPT),
            "caption_lines": [title, local, _ARROW + " " + remote],
        }]
