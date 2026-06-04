"""
Screen manager that instantiates all screens once at boot.
"""

import gc

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
        self._cleanup_screen = None
        mem_snapshot("screen.init.done", enabled=_DEBUG, collect=True)

    def _create_lazy_screen(self, screen_id):
        if screen_id in self._screens:
            return
        if screen_id == screen_ids.LAUNCHER:
            mem_snapshot("screen.lazy.launcher.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = LauncherScreen(i18n=self._i18n)
            mem_snapshot("screen.lazy.launcher", enabled=_DEBUG, collect=True)
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
            return
        if screen_id == screen_ids.CALIBRATION_WIZARD:
            mem_snapshot("screen.lazy.calibration.before_import", enabled=_DEBUG, collect=True)
            from ui.scale_calibration_wizard_screen import ScaleCalibrationWizardScreen

            mem_snapshot("screen.lazy.calibration.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = ScaleCalibrationWizardScreen(i18n=self._i18n)
            mem_snapshot("screen.lazy.calibration", enabled=_DEBUG, collect=True)

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

    def release_all(self, keep_ids=()):
        keep = set(keep_ids or ())
        if self._active_id is not None and self._active_id not in keep:
            self._load_cleanup_screen()
        for screen_id in list(self._screens.keys()):
            if screen_id in keep:
                continue
            screen = self._screens.pop(screen_id, None)
            if screen is None:
                continue
            try:
                screen.root().delete()
            except Exception:
                pass
        if self._active_id not in self._screens:
            self._active_id = None

    def _load_cleanup_screen(self):
        try:
            import lvgl as lv

            if self._cleanup_screen is None:
                self._cleanup_screen = lv.obj()
                try:
                    self._cleanup_screen.set_style_bg_color(lv.color_hex(0x000000), 0)
                    self._cleanup_screen.set_style_bg_opa(255, 0)
                except Exception:
                    pass

            loader = getattr(lv, "screen_load", None)
            if loader:
                loader(self._cleanup_screen)
            else:
                loader = getattr(lv, "scr_load", None)
                if loader:
                    loader(self._cleanup_screen)
                elif hasattr(self._cleanup_screen, "screen_load"):
                    self._cleanup_screen.screen_load()
        except Exception:
            pass

    def memory_cleanup(self, keep_ids=(), loading_message=None):
        keep = tuple(keep_ids or ())
        if loading_message:
            keep = self._show_loading_screen(loading_message, keep)
        self.release_all(keep_ids=keep)
        try:
            import lvgl as lv

            lv.image_cache_drop(None)
        except Exception:
            pass
        gc.collect()
        gc.collect()
        mem_snapshot("screen.memory_cleanup", enabled=_DEBUG, collect=False)

    def _show_loading_screen(self, message, keep_ids):
        try:
            screen = self.get(screen_ids.SIMPLE_MESSAGE)
            if screen is None:
                return keep_ids
            screen.configure(
                title="",
                message=message,
                title_bg_color=0x333333,
                show_ok_button=False,
            )
            self.show(screen_ids.SIMPLE_MESSAGE)
            try:
                import lvgl as lv

                lv.task_handler()
            except Exception:
                pass
            return tuple(keep_ids) + (screen_ids.SIMPLE_MESSAGE,)
        except Exception:
            return keep_ids

    def active_screen_id(self):
        return self._active_id
