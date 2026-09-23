"""
Screen manager that lazy-loads screens to keep heap pressure low.
"""

import sys

import runtime_debug
from ui import screen_ids


def _trace(message):
    runtime_debug.log("[TRACE] {}".format(message))


def _trace_lvgl_state(label, cleanup=None, target=None):
    if not runtime_debug.DEBUG:
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


# One table for both ends of a screen's life: what to import to build it, and
# what to evict once it is deleted. They used to be an if-chain and a separate
# dict, so a screen could be created but never evicted.
#   screen id: (module, class, takes an i18n argument)
_SCREEN_SPECS = {
    screen_ids.LAUNCHER: ("ui.launcher_screen", "LauncherScreen", True),
    screen_ids.SELECT_ITEM: ("ui.select_item_screen", "SelectItemScreen", False),
    screen_ids.WEIGHT: ("ui.weight_screen", "WeightScreen", True),
    screen_ids.KEG_VOLUME: ("ui.keg_volume_screen", "KegVolumeScreen", True),
    screen_ids.SIMPLE_MESSAGE: ("ui.simple_message_screen", "SimpleMessageScreen", True),
    screen_ids.SETTINGS: ("ui.settings_screen", "SettingsScreen", True),
    screen_ids.UPDATER: ("ui.updater_screen", "UpdaterScreen", True),
    screen_ids.CALIBRATION_WIZARD: (
        "ui.scale_calibration_wizard_screen",
        "ScaleCalibrationWizardScreen",
        True,
    ),
}

# The launcher screen is kept alive across transitions as the fallback root,
# so its module must never be evicted.
_PERMANENT_SCREEN_IDS = (screen_ids.LAUNCHER,)


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
        runtime_debug.collect()
        runtime_debug.snapshot("screen.init.start", collect=True)
        self._i18n = i18n
        self._screens = {}
        if initial_screen_id == screen_ids.LAUNCHER:
            self._screens[screen_ids.LAUNCHER] = self._new_launcher_screen()
            runtime_debug.collect()
            runtime_debug.snapshot("screen.after_launcher", collect=True)
        self._active_id = None
        self._cleanup_screen = None
        runtime_debug.collect()
        runtime_debug.snapshot("screen.init.done", collect=True)

    def _new_launcher_screen(self):
        return self._build_screen(screen_ids.LAUNCHER)

    def _build_screen(self, screen_id):
        """Import the screen module and construct it, tracing both steps.

        The import and the constructor are traced separately on purpose: on
        the Dial they fail for different reasons, the first on fragmented C
        heap and the second on LVGL allocations.
        """
        spec = _SCREEN_SPECS.get(screen_id)
        if spec is None:
            return None
        module_name, class_name, wants_i18n = spec
        short = screen_id
        runtime_debug.collect()
        runtime_debug.snapshot("screen.lazy.{}.before_import".format(short), collect=True)
        module = __import__(module_name, None, None, ("*",))
        screen_class = getattr(module, class_name)
        runtime_debug.collect()
        runtime_debug.snapshot("screen.lazy.{}.before_ctor".format(short), collect=True)
        screen = screen_class(i18n=self._i18n) if wants_i18n else screen_class()
        runtime_debug.collect()
        runtime_debug.snapshot("screen.lazy.{}".format(short), collect=True)
        return screen

    def _create_lazy_screen(self, screen_id):
        if screen_id in self._screens:
            return
        screen = self._build_screen(screen_id)
        if screen is not None:
            self._screens[screen_id] = screen

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
            if screen_id in _PERMANENT_SCREEN_IDS:
                continue
            spec = _SCREEN_SPECS.get(screen_id)
            if spec:
                _evict_module(spec[0])

    def release(self, screen_id):
        runtime_debug.snapshot(
            "screen.release.before.{}".format(screen_id),
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
        runtime_debug.collect()
        runtime_debug.snapshot(
            "screen.release.after.{}".format(screen_id),
            collect=False,
        )

    def release_all(
        self,
        keep_ids=(),
        cleanup_message=None,
        cleanup_color=0x333333,
    ):
        keep = set(keep_ids or ())
        runtime_debug.snapshot("screen.release_all.before", collect=False)
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
        runtime_debug.collect()
        runtime_debug.snapshot("screen.release_all.after", collect=False)
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
        runtime_debug.snapshot("screen.memory_cleanup.before", collect=False)
        keep = list(keep_ids or ())
        if screen_ids.LAUNCHER not in keep:
            keep.append(screen_ids.LAUNCHER)
        self.release_all(
            keep_ids=tuple(keep),
            cleanup_message=loading_message,
            cleanup_color=loading_color,
        )
        runtime_debug.collect(cycles=2)
        runtime_debug.snapshot("screen.memory_cleanup.after", collect=False)

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
