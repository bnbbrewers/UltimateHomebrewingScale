"""
Memory-safe keg filler app (business logic only).
"""

from .base_app import BaseApp
from ui import screen_ids


class KegFillerApp(BaseApp):
    APP_ID = "keg_filler_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = None
        self._scale = self.hardware.scale
        self._density = 1.01

    def _weight(self):
        if self._screen is None:
            self._screen = self.screen_manager.get(screen_ids.WEIGHT)
        return self._screen

    def on_enter(self):
        super().on_enter()
        self.screen_manager.show(screen_ids.WEIGHT)
        screen = self._weight()
        screen.configure(
            title=self.t("keg.title"),
            mode="countdown_l",
            target=0,
            title_bg_color=0x607D8B,
            tolerance=0,
        )
        screen.set_status("WIP - long press to launcher")

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"
        if self._scale is None:
            self._weight().set_status("Scale not found")
            return None
        weight = self._scale.read_weight_filtered()
        if weight is None:
            return None
        self._weight().update_from_weight(weight)
        return None
