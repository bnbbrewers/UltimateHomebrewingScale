"""
Screen manager that instantiates all screens once at boot.
"""

from ui import screen_ids
from ui.launcher_screen import LauncherScreen
from ui.select_item_screen import SelectItemScreen
from ui.weight_screen import WeightScreen
from ui.simple_message_screen import SimpleMessageScreen


class ScreenManager:
    def __init__(self, i18n=None):
        launcher = LauncherScreen(i18n=i18n)
        select = SelectItemScreen()
        weight = WeightScreen(i18n=i18n)
        simple = SimpleMessageScreen(i18n=i18n)
        self._screens = {
            screen_ids.LAUNCHER: launcher,
            screen_ids.SELECT_ITEM: select,
            screen_ids.WEIGHT: weight,
            screen_ids.SIMPLE_MESSAGE: simple,
        }
        self._active_id = None

    def get(self, screen_id):
        return self._screens.get(screen_id)

    def show(self, screen_id):
        screen = self._screens.get(screen_id)
        if screen is None:
            return
        self._active_id = screen_id
        screen.root().screen_load()

    def active_screen_id(self):
        return self._active_id
