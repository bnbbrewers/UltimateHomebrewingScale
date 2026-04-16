"""
Launcher app controller (business logic only).
"""

from .base_app import BaseApp
from ui import screen_ids

LAUNCHER_ITEMS = [
    {
        "label": "Scale",
        "icon": "/flash/assets/icons/Scale.png",
        "module": "scale_app",
        "color": 0x00A8E8,
        "order": 0,
    },
    {
        "label": "Malt",
        "icon": "/flash/assets/icons/Malt.png",
        "module": "malt_app",
        "color": 0xD4840A,
        "order": 1,
    },
    {
        "label": "Hop",
        "icon": "/flash/assets/icons/Hop.png",
        "module": "hop_app",
        "color": 0x388E3C,
        "order": 2,
    },
    {
        "label": "Keg",
        "icon": "/flash/assets/icons/Keg.png",
        "module": "keg_filler_app",
        "color": 0x607D8B,
        "order": 3,
    },
    {
        "label": "Settings",
        "icon": "/flash/assets/icons/Parameters.png",
        "module": "settings_app",
        "color": 0x546E7A,
        "order": 4,
    },
]


class LauncherApp(BaseApp):
    APP_ID = "launcher"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = self.screen_manager.get(screen_ids.LAUNCHER)
        self._rotary = self.hardware.rotary
        self._items = LAUNCHER_ITEMS
        self._selected = 0

    def on_exit(self):
        super().on_exit()

    def on_enter(self):
        super().on_enter()
        try:
            import gc, config
            if getattr(config, "DEBUG", False):
                gc.collect()
                print("[MEM] launcher.on_enter free={}".format(gc.mem_free()))
        except Exception:
            pass
        self.screen_manager.show(screen_ids.LAUNCHER)
        self._screen.set_items(self._items)
        self._selected = 0
        self._screen.set_selected_index(self._selected)
        if self._rotary:
            self._rotary.reset_rotary_value()

    def tick(self):
        if self._rotary:
            delta = self._rotary.get_rotary_value()
            if delta:
                self._rotary.reset_rotary_value()
                self._screen.handle_rotary_delta(delta)
                self._selected = self._screen.get_selected_index()
        self._screen.animate_indicator()

        if self.hardware.button.was_short_pressed():
            if not self._items:
                return None
            return self._items[self._selected].get("module")
        return None
