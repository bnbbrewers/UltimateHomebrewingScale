"""
Memory-safe scale app (business logic only).
"""

import time

from .base_app import BaseApp
from ui import screen_ids


class ScaleApp(BaseApp):
    APP_ID = "scale_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = None
        self._scale = self.hardware.scale

        self._status_reset_at = 0
        self._last_weight = None

    def _weight(self):
        if self._screen is None:
            self._screen = self.screen_manager.get(screen_ids.WEIGHT)
        return self._screen

    def on_enter(self):
        super().on_enter()
        self.screen_manager.show(screen_ids.WEIGHT)
        screen = self._weight()
        screen.configure(
            title=self.t("scale.title"),
            mode="simple",
            target=0,
            title_bg_color=0x1E40AF,
            tolerance=0,
        )
        if self._scale:
            screen.set_status(self.t("scale.taring"))
            if self._scale.tare():
                screen.set_status(self.t("scale.tare_done"))
                self._last_weight = None
                self._status_reset_at = time.ticks_add(time.ticks_ms(), 1200)
            else:
                screen.set_status(self.t("scale.tare_error"))
                self._status_reset_at = time.ticks_add(time.ticks_ms(), 1200)
        else:
            screen.set_status(self.t("scale.tare_ready"))

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"

        if self._scale is None:
            self._weight().set_status("Scale not found")
            return None

        if self.hardware.button and self.hardware.button.was_short_pressed():
            self._weight().set_status(self.t("scale.taring"))
            ok = self._scale.tare()
            if ok:
                self._weight().set_status(self.t("scale.tare_done"))
                self._last_weight = None
            else:
                self._weight().set_status(self.t("scale.tare_error"))
            self._status_reset_at = time.ticks_add(time.ticks_ms(), 1200)

        if self._status_reset_at:
            if time.ticks_diff(time.ticks_ms(), self._status_reset_at) >= 0:
                self._status_reset_at = 0
                self._weight().set_status(self.t("scale.tare_ready"))

        weight = self._scale.read_weight_filtered()
        if weight is None:
            return None

        if self._last_weight != weight:
            self._weight().update_from_weight(weight)
        self._last_weight = weight
        return None
