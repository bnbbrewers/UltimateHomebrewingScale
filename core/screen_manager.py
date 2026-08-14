"""
Screen manager that lazy-loads screens to keep heap pressure low.
"""

import gc
import sys

from ui import screen_ids

try:
    import config
    _DEBUG = getattr(config, "DEBUG", False)
except Exception:
    _DEBUG = False

if _DEBUG:
    try:
        from memory_debug import snapshot as _debug_snapshot
    except Exception:
        _debug_snapshot = None
else:
    _debug_snapshot = None


def _collect_runtime(cycles=1):
    for _ in range(max(1, cycles)):
        gc.collect()


def _mem_snapshot(tag, enabled=True, collect=False):
    if enabled and _debug_snapshot:
        _debug_snapshot(tag, enabled=True, collect=collect)


def _trace(message):
    if not _DEBUG:
        return
    try:
        print("[TRACE] {}".format(message))
    except Exception:
        pass


def _trace_lvgl_state(label, cleanup=None, target=None):
    if not _DEBUG:
        return
    try:
        import lvgl as lv

        getter = getattr(lv, "screen_active", None)
        if getter is None:
            getter = getattr(lv, "scr_act", None)
        active = getter() if getter else None
        print(
            "[TRACE] {} active={} cleanup={} target={}".format(
                label,
                id(active) if active is not None else None,
                id(cleanup) if cleanup is not None else None,
                id(target) if target is not None else None,
            )
        )
    except Exception:
        pass


_SCREEN_MODULES = {
    screen_ids.SELECT_ITEM: "ui.select_item_screen",
    screen_ids.WEIGHT: "ui.weight_screen",
    screen_ids.KEG_VOLUME: "ui.keg_volume_screen",
    screen_ids.SIMPLE_MESSAGE: "ui.simple_message_screen",
    screen_ids.SETTINGS: "ui.settings_screen",
    screen_ids.UPDATER: "ui.updater_screen",
    screen_ids.CALIBRATION_WIZARD: "ui.scale_calibration_wizard_screen",
}


def _evict_module(module_name):
    if not module_name:
        return
    module = sys.modules.pop(module_name, None)
    if module is None:
        return
    package_name, _, child_name = module_name.rpartition(".")
    package = sys.modules.get(package_name)
    if package is None:
        return
    try:
        if getattr(package, child_name, None) is module:
            delattr(package, child_name)
    except Exception:
        pass


class ScreenManager:
    def __init__(self, i18n=None, initial_screen_id=None):
        _collect_runtime()
        _mem_snapshot("screen.init.start", enabled=_DEBUG, collect=True)
        self._i18n = i18n
        self._screens = {}
        if initial_screen_id == screen_ids.LAUNCHER:
            self._screens[screen_ids.LAUNCHER] = self._new_launcher_screen()
            _collect_runtime()
            _mem_snapshot("screen.after_launcher", enabled=_DEBUG, collect=True)
        self._active_id = None
        self._cleanup_screen = None
        _collect_runtime()
        _mem_snapshot("screen.init.done", enabled=_DEBUG, collect=True)

    def _new_launcher_screen(self):
        from ui.launcher_screen import LauncherScreen

        return LauncherScreen(i18n=self._i18n)

    def _create_lazy_screen(self, screen_id):
        if screen_id in self._screens:
            return
        if screen_id == screen_ids.LAUNCHER:
            _collect_runtime()
            _mem_snapshot("screen.lazy.launcher.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = self._new_launcher_screen()
            _collect_runtime()
            _mem_snapshot("screen.lazy.launcher", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.SELECT_ITEM:
            _collect_runtime()
            _mem_snapshot("screen.lazy.select.before_import", enabled=_DEBUG, collect=True)
            from ui.select_item_screen import SelectItemScreen

            _collect_runtime()
            _mem_snapshot("screen.lazy.select.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = SelectItemScreen()
            _collect_runtime()
            _mem_snapshot("screen.lazy.select", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.WEIGHT:
            _collect_runtime()
            _mem_snapshot("screen.lazy.weight.before_import", enabled=_DEBUG, collect=True)
            from ui.weight_screen import WeightScreen

            _collect_runtime()
            _mem_snapshot("screen.lazy.weight.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = WeightScreen(i18n=self._i18n)
            _collect_runtime()
            _mem_snapshot("screen.lazy.weight", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.KEG_VOLUME:
            _collect_runtime()
            _mem_snapshot("screen.lazy.keg_volume.before_import", enabled=_DEBUG, collect=True)
            from ui.keg_volume_screen import KegVolumeScreen

            _collect_runtime()
            _mem_snapshot("screen.lazy.keg_volume.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = KegVolumeScreen(i18n=self._i18n)
            _collect_runtime()
            _mem_snapshot("screen.lazy.keg_volume", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.SIMPLE_MESSAGE:
            _collect_runtime()
            _mem_snapshot("screen.lazy.simple.before_import", enabled=_DEBUG, collect=True)
            from ui.simple_message_screen import SimpleMessageScreen

            _collect_runtime()
            _mem_snapshot("screen.lazy.simple.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = SimpleMessageScreen(i18n=self._i18n)
            _collect_runtime()
            _mem_snapshot("screen.lazy.simple", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.SETTINGS:
            _collect_runtime()
            _mem_snapshot("screen.lazy.settings.before_import", enabled=_DEBUG, collect=True)
            from ui.settings_screen import SettingsScreen

            _collect_runtime()
            _mem_snapshot("screen.lazy.settings.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = SettingsScreen(i18n=self._i18n)
            _collect_runtime()
            _mem_snapshot("screen.lazy.settings", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.UPDATER:
            _collect_runtime()
            _mem_snapshot("screen.lazy.updater.before_import", enabled=_DEBUG, collect=True)
            from ui.updater_screen import UpdaterScreen

            _collect_runtime()
            _mem_snapshot("screen.lazy.updater.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = UpdaterScreen(i18n=self._i18n)
            _collect_runtime()
            _mem_snapshot("screen.lazy.updater", enabled=_DEBUG, collect=True)
            return
        if screen_id == screen_ids.CALIBRATION_WIZARD:
            _collect_runtime()
            _mem_snapshot("screen.lazy.calibration.before_import", enabled=_DEBUG, collect=True)
            from ui.scale_calibration_wizard_screen import ScaleCalibrationWizardScreen

            _collect_runtime()
            _mem_snapshot("screen.lazy.calibration.before_ctor", enabled=_DEBUG, collect=True)
            self._screens[screen_id] = ScaleCalibrationWizardScreen(i18n=self._i18n)
            _collect_runtime()
            _mem_snapshot("screen.lazy.calibration", enabled=_DEBUG, collect=True)

    def get(self, screen_id):
        self._create_lazy_screen(screen_id)
        return self._screens.get(screen_id)

    def show(self, screen_id):
        # A cleanup transition may already have loaded the launcher as the
        # fallback screen before the target app's on_enter() is called. Do not
        # load the same LVGL root twice: apart from being unnecessary, the
        # second native screen_load() can fail when the heap is fragmented.
        if self._active_id == screen_id and screen_id in self._screens:
            return
        screen = self.get(screen_id)
        if screen is None:
            return
        self._active_id = screen_id
        _trace("screen.show.before_load {}".format(screen_id))
        screen.root().screen_load()
        _trace("screen.show.after_load {}".format(screen_id))

    @staticmethod
    def _release_screen_resources(screen):
        release_resources = getattr(screen, "release_resources", None)
        if release_resources:
            try:
                release_resources()
            except Exception:
                pass

    @classmethod
    def _delete_screen(cls, screen):
        """Delete the LVGL tree, then release resources owned by that tree."""
        try:
            screen.root().delete()
        except Exception:
            pass
        finally:
            # Native resources such as binfonts may still be referenced by
            # widgets until the root tree has been deleted.
            cls._release_screen_resources(screen)

    @staticmethod
    def _evict_screen_modules(screen_ids_to_release):
        for screen_id in screen_ids_to_release:
            module_name = _SCREEN_MODULES.get(screen_id)
            if module_name:
                _evict_module(module_name)

    def release(self, screen_id):
        _mem_snapshot(
            "screen.release.before.{}".format(screen_id),
            enabled=_DEBUG,
            collect=False,
        )
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
            self._delete_screen(screen)
        except Exception:
            pass
        self._evict_screen_modules((screen_id,))
        _collect_runtime()
        _mem_snapshot(
            "screen.release.after.{}".format(screen_id),
            enabled=_DEBUG,
            collect=False,
        )

    def release_all(
        self,
        keep_ids=(),
        cleanup_message=None,
        cleanup_color=0x333333,
    ):
        keep = set(keep_ids or ())
        _mem_snapshot("screen.release_all.before", enabled=_DEBUG, collect=False)
        # Keep the active screen valid while deleting the outgoing tree. LVGL
        # does not support deleting the currently active screen, so always
        # switch to the small persistent transition screen first.
        if cleanup_message is not None or (
            self._active_id is not None and self._active_id not in keep
        ):
            self._load_cleanup_screen(
                cleanup_message,
                cleanup_color,
                clear_message=cleanup_message is None,
            )
        released_screen_ids = []
        for screen_id in list(self._screens.keys()):
            if screen_id in keep:
                continue
            screen = self._screens.pop(screen_id, None)
            if screen is None:
                continue
            try:
                self._delete_screen(screen)
            except Exception:
                pass
            released_screen_ids.append(screen_id)
        self._evict_screen_modules(released_screen_ids)
        _collect_runtime()
        _mem_snapshot("screen.release_all.after", enabled=_DEBUG, collect=False)
        if self._active_id not in self._screens:
            self._active_id = None

    def _load_cleanup_screen(
            self, message=None, loading_color=0x333333, clear_message=False):
        try:
            import lvgl as lv

            if self._cleanup_screen is None:
                self._cleanup_screen = lv.obj()
                self._cleanup_label = None
                try:
                    self._cleanup_screen.set_style_bg_color(lv.color_hex(0x000000), 0)
                    self._cleanup_screen.set_style_bg_opa(255, 0)
                except Exception:
                    pass
            if message:
                if getattr(self, "_cleanup_label", None) is None:
                    self._cleanup_label = lv.label(self._cleanup_screen)
                    try:
                        self._cleanup_label.set_width(220)
                    except Exception:
                        pass
                    try:
                        self._cleanup_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
                    except Exception:
                        pass
                try:
                    self._cleanup_label.set_text(message)
                except Exception:
                    pass
                try:
                    self._cleanup_label.set_style_text_color(lv.color_hex(0xE5E7EB), 0)
                except Exception:
                    pass
                try:
                    self._cleanup_label.align(lv.ALIGN.CENTER, 0, 0)
                except Exception:
                    try:
                        self._cleanup_label.set_pos(20, 110)
                    except Exception:
                        pass
            elif clear_message and getattr(self, "_cleanup_label", None) is not None:
                try:
                    self._cleanup_label.set_text("")
                except Exception:
                    pass

            loader = getattr(lv, "screen_load", None)
            _trace("screen.cleanup.before_load")
            if loader:
                loader(self._cleanup_screen)
            else:
                loader = getattr(lv, "scr_load", None)
                if loader:
                    loader(self._cleanup_screen)
                elif hasattr(self._cleanup_screen, "screen_load"):
                    self._cleanup_screen.screen_load()
            _trace("screen.cleanup.after_load")
            _trace_lvgl_state(
                "screen.cleanup.state_after_load",
                cleanup=self._cleanup_screen,
            )
        except Exception:
            pass

    def memory_cleanup(
        self,
        keep_ids=(),
        loading_message=None,
        loading_color=0x333333,
    ):
        _mem_snapshot("screen.memory_cleanup.before", enabled=_DEBUG, collect=False)
        keep = list(keep_ids or ())
        if screen_ids.LAUNCHER not in keep:
            keep.append(screen_ids.LAUNCHER)
        self.release_all(
            keep_ids=tuple(keep),
            cleanup_message=loading_message,
            cleanup_color=loading_color,
        )
        _collect_runtime(cycles=2)
        _mem_snapshot("screen.memory_cleanup.after", enabled=_DEBUG, collect=False)

    def release_cleanup_screen(self):
        """Keep the lightweight transition screen for later reuse.

        Deleting this LVGL root during an app transition can schedule native
        work in the M5UI port while the launcher is being rendered. Keeping
        one inactive instance avoids that fragile delete path and prevents
        repeated allocation/deallocation of the transition tree.
        """
        screen = self._cleanup_screen
        if screen is None:
            return
        _trace("screen.cleanup.retain")
        target = None
        if self._active_id in self._screens:
            try:
                target = self._screens[self._active_id].root()
            except Exception:
                target = None
        _trace_lvgl_state(
            "screen.cleanup.state_retained",
            cleanup=screen,
            target=target,
        )

    def active_screen_id(self):
        return self._active_id
