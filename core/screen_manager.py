"""
Screen manager that instantiates all screens once at boot.
"""

from ui import screen_ids
from ui.launcher_screen import LauncherScreen
from memory_debug import snapshot as mem_snapshot

try:
    import config
    _DEBUG = getattr(config, "DEBUG", False)
except Exception:
    _DEBUG = False


class ScreenManager:
    def __init__(self, i18n=None):
        mem_snapshot("screen.init.start", enabled=_DEBUG, collect=True)
        self._i18n = i18n
        launcher = LauncherScreen(i18n=i18n)
        mem_snapshot("screen.after_launcher", enabled=_DEBUG, collect=True)
        self._screens = {
            screen_ids.LAUNCHER: launcher,
        }
        self._active_id = None
        mem_snapshot("screen.init.done", enabled=_DEBUG, collect=True)

    def _create_lazy_screen(self, screen_id):
        if screen_id in self._screens:
            return
        if screen_id == screen_ids.SELECT_ITEM:
            from ui.select_item_screen import SelectItemScreen

            self._screens[screen_id] = SelectItemScreen()
            mem_snapshot("screen.lazy.select", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.WEIGHT:
            from ui.weight_screen import WeightScreen

            self._screens[screen_id] = WeightScreen(i18n=self._i18n)
            mem_snapshot("screen.lazy.weight", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.SIMPLE_MESSAGE:
            from ui.simple_message_screen import SimpleMessageScreen

            self._screens[screen_id] = SimpleMessageScreen(i18n=self._i18n)
            mem_snapshot("screen.lazy.simple", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.SETUP_QR:
            from ui.setup_qr_screen import SetupQrScreen

            self._screens[screen_id] = SetupQrScreen(i18n=self._i18n)
            mem_snapshot("screen.lazy.setup_qr", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.UPDATER:
            from ui.updater_screen import UpdaterScreen

            self._screens[screen_id] = UpdaterScreen(i18n=self._i18n)
            mem_snapshot("screen.lazy.updater", enabled=_DEBUG, collect=True)

    def get(self, screen_id):
        self._create_lazy_screen(screen_id)
        return self._screens.get(screen_id)

    def show(self, screen_id):
        screen = self.get(screen_id)
        if screen is None:
            return
        self._active_id = screen_id
        screen.root().screen_load()

    def active_screen_id(self):
        return self._active_id
