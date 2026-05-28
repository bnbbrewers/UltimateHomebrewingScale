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
            mem_snapshot("screen.lazy.select.before_import", enabled=_DEBUG, collect=True)
            from ui.select_item_screen import SelectItemScreen

            mem_snapshot("screen.lazy.select.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = SelectItemScreen()
            mem_snapshot("screen.lazy.select", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.WEIGHT:
            mem_snapshot("screen.lazy.weight.before_import", enabled=_DEBUG, collect=True)
            from ui.weight_screen import WeightScreen

            mem_snapshot("screen.lazy.weight.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = WeightScreen(i18n=self._i18n)
            mem_snapshot("screen.lazy.weight", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.KEG_VOLUME:
            mem_snapshot("screen.lazy.keg_volume.before_import", enabled=_DEBUG, collect=True)
            from ui.keg_volume_screen import KegVolumeScreen

            mem_snapshot("screen.lazy.keg_volume.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = KegVolumeScreen(i18n=self._i18n)
            mem_snapshot("screen.lazy.keg_volume", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.SIMPLE_MESSAGE:
            mem_snapshot("screen.lazy.simple.before_import", enabled=_DEBUG, collect=True)
            from ui.simple_message_screen import SimpleMessageScreen

            mem_snapshot("screen.lazy.simple.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = SimpleMessageScreen(i18n=self._i18n)
            mem_snapshot("screen.lazy.simple", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.SETTINGS:
            mem_snapshot("screen.lazy.settings.before_import", enabled=_DEBUG, collect=True)
            from ui.settings_screen import SettingsScreen

            mem_snapshot("screen.lazy.settings.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = SettingsScreen(i18n=self._i18n)
            mem_snapshot("screen.lazy.settings", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.UPDATER:
            mem_snapshot("screen.lazy.updater.before_import", enabled=_DEBUG, collect=True)
            from ui.updater_screen import UpdaterScreen

            mem_snapshot("screen.lazy.updater.before_ctor", enabled=_DEBUG, collect=True)
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

    def release(self, screen_id):
        screen = self._screens.pop(screen_id, None)
        if screen is None:
            return
        if self._active_id == screen_id:
            fallback = self._screens.get(screen_ids.LAUNCHER)
            if screen_id == screen_ids.LAUNCHER or fallback is None:
                self._screens[screen_id] = screen
                return
            try:
                fallback.root().screen_load()
                self._active_id = screen_ids.LAUNCHER
            except Exception:
                self._screens[screen_id] = screen
                return
        try:
            screen.root().delete()
        except Exception:
            pass

    def active_screen_id(self):
        return self._active_id
