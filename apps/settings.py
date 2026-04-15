"""
Memory-safe settings app (business logic only).
"""

from .base_app import BaseApp
from ui import screen_ids


class SettingsApp(BaseApp):
    APP_ID = "settings"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = self.screen_manager.get(screen_ids.SELECT_ITEM)
        self._rotary = self.hardware.rotary
        self._selected = 0
        self._item_keys = [
            "settings.language",
            "settings.calibration",
            "settings.about",
        ]
        self._item_labels = []

    def on_enter(self):
        super().on_enter()
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        self._selected = 0
        self._item_labels = []
        for key in self._item_keys:
            self._item_labels.append(self.t(key))
        self._screen.configure(
            title=self.t("settings.title"),
            items=self._item_labels,
            accent_color=0x546E7A,
            selected_index=self._selected,
        )
        if self._rotary:
            self._rotary.reset_rotary_value()

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"
        if self._rotary:
            delta = self._rotary.get_rotary_value()
            if delta:
                self._rotary.reset_rotary_value()
                if delta > 0:
                    self._selected += 1
                else:
                    self._selected -= 1
                if self._selected < 0:
                    self._selected = 0
                if self._selected >= len(self._item_labels):
                    self._selected = len(self._item_labels) - 1
                self._screen.set_selected_index(self._selected)
        if self.hardware.button.was_short_pressed():
            self._screen.set_title("Not implemented")
        return None
