"""
Memory-safe scale app (business logic only).
"""

import time

from .base_app import BaseApp
from ui import screen_ids


class ScaleApp(BaseApp):
    APP_ID = "scale"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = self.screen_manager.get(screen_ids.WEIGHT)
        self._scale = self.hardware.scale

        self._status_reset_at = 0
        self._last_weight = None
        self._long_press_handled = False

    def on_enter(self):
        super().on_enter()
        self._long_press_handled = False
        self.screen_manager.show(screen_ids.WEIGHT)
        self._screen.configure(
            title=self.t("scale.title"),
            mode="simple",
            target=0,
            title_bg_color=0x1E40AF,
            tolerance=0,
        )
        if self._scale:
            self._screen.set_status(self.t("scale.taring"))
            if self._scale.tare():
                self._screen.set_status(self.t("scale.tare_done"))
                self._last_weight = None
                self._status_reset_at = time.ticks_add(time.ticks_ms(), 1200)
            else:
                self._screen.set_status(self.t("scale.tare_error"))
                self._status_reset_at = time.ticks_add(time.ticks_ms(), 1200)
        else:
            self._screen.set_status(self.t("scale.tare_ready"))

    def tick(self):
        if self._scale is None:
            self._screen.set_status("Scale not found")
            return None

        button = self.hardware.button
        if button:
            now = time.ticks_ms()
            is_pressed = button.isPressed()

            if is_pressed:
                if not self._btn_is_pressed:
                    self._btn_is_pressed = True
                    self._btn_press_start = now
                    self._long_press_handled = False
                elif not self._long_press_handled:
                    elapsed = time.ticks_diff(now, self._btn_press_start)
                    if elapsed >= self.LONG_PRESS_DURATION_MS:
                        self._long_press_handled = True
                        self._btn_is_pressed = False
                        return "launcher"
            else:
                if self._btn_is_pressed:
                    elapsed = time.ticks_diff(now, self._btn_press_start)
                    self._btn_is_pressed = False
                    if elapsed < self.LONG_PRESS_DURATION_MS and not self._long_press_handled:
                        self._screen.set_status(self.t("scale.taring"))
                        ok = self._scale.tare()
                        if ok:
                            self._screen.set_status(self.t("scale.tare_done"))
                            self._last_weight = None
                        else:
                            self._screen.set_status(self.t("scale.tare_error"))
                        self._status_reset_at = time.ticks_add(time.ticks_ms(), 1200)
                self._long_press_handled = False

        if self._status_reset_at:
            if time.ticks_diff(time.ticks_ms(), self._status_reset_at) >= 0:
                self._status_reset_at = 0
                self._screen.set_status(self.t("scale.tare_ready"))

        weight = self._scale.read_weight()
        if weight is None:
            return None

        if self._last_weight != weight:
            self._screen.update_from_weight(weight)
        self._last_weight = weight
        return None
