"""
Memory-safe hop assistant app (business logic only).
"""

from .base_app import BaseApp
from ui import screen_ids


class HopAssistantApp(BaseApp):
    APP_ID = "hop_assistant"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = self.screen_manager.get(screen_ids.WEIGHT)
        self._scale = self.hardware.scale

    def on_enter(self):
        super().on_enter()
        self.screen_manager.show(screen_ids.WEIGHT)
        self._screen.configure(
            title=self.t("hop.title"),
            mode="simple",
            target=0,
            title_bg_color=0x388E3C,
            tolerance=0,
        )
        self._screen.set_status("WIP - long press to launcher")

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"
        if self._scale is None:
            self._screen.set_status("Scale not found")
            return None
        weight = self._scale.read_weight()
        if weight is None:
            return None
        self._screen.update_from_weight(weight)
        return None
