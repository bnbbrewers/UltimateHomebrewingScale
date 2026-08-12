"""
App manager with persistent one-time app instances.
"""

import gc
import os
import sys

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


CALIBRATION_FILE = "scale_calibration.json"
CALIBRATION_WIZARD_APP_ID = "scale_calibration_wizard_app"


def _collect_runtime(cycles=1):
    for _ in range(max(1, cycles)):
        gc.collect()


def _mem_snapshot(tag, enabled=True, collect=False):
    if enabled and _debug_snapshot:
        _debug_snapshot(tag, enabled=True, collect=collect)


def _file_exists(path):
    try:
        return os.path.exists(path)
    except AttributeError:
        try:
            os.stat(path)
            return True
        except OSError:
            return False


def _initial_app_id(initial_app_id=None):
    if initial_app_id:
        return initial_app_id
    if _file_exists(CALIBRATION_FILE):
        return "launcher"
    return CALIBRATION_WIZARD_APP_ID


class AppManager:
    def __init__(self, screen_manager, hardware, apis, i18n=None, initial_app_id=None):
        _collect_runtime()
        _mem_snapshot("app.init.start", enabled=_DEBUG, collect=True)
        self._screen_manager = screen_manager
        self._i18n = i18n
        self._apis = apis
        self._apps = {}
        # Only the active app is created during boot: the main loop needs one
        # app to tick, but every other app stays lazy until the launcher or
        # startup flow selects it. This keeps C/Python heap pressure low.
        self._active_app_id = _initial_app_id(initial_app_id=initial_app_id)
        self._ensure_app(self._active_app_id, screen_manager, hardware, apis, i18n)
        _collect_runtime()
        _mem_snapshot("app.after_initial_app", enabled=_DEBUG, collect=True)
        self._apps[self._active_app_id].on_enter()
        _collect_runtime()
        _mem_snapshot("app.after_on_enter", enabled=_DEBUG, collect=True)

    def _ensure_app(self, app_id, screen_manager=None, hardware=None, apis=None, i18n=None):
        if app_id in self._apps:
            return True
        if app_id == "launcher":
            self._create_launcher(screen_manager, hardware, apis, i18n)
            return True
        if app_id == "scale_app":
            self._create_scale(screen_manager, hardware, apis, i18n)
            return True
        if app_id == "malt_app":
            self._create_malt(screen_manager, hardware, apis, i18n)
            return True
        if app_id == "hop_app":
            self._create_hop(screen_manager, hardware, apis, i18n)
            return True
        if app_id == "keg_filler_app":
            self._create_keg(screen_manager, hardware, apis, i18n)
            return True
        if app_id == "settings_app":
            from apps.settings_app import SettingsApp

            self._apps[app_id] = SettingsApp(
                screen_manager,
                hardware,
                apis,
                i18n=i18n,
            )
            _collect_runtime()
            _mem_snapshot("app.lazy.settings_created", enabled=_DEBUG, collect=True)
            return True
        if app_id == CALIBRATION_WIZARD_APP_ID:
            from apps.scale_calibration_wizard_app import ScaleCalibrationWizardApp

            self._apps[app_id] = ScaleCalibrationWizardApp(
                screen_manager,
                hardware,
                apis,
                i18n=i18n,
            )
            _collect_runtime()
            _mem_snapshot("app.lazy.calibration_created", enabled=_DEBUG, collect=True)
            return True
        if app_id == "updater_app":
            from updater.update_app import UpdaterApp

            self._apps[app_id] = UpdaterApp(
                screen_manager,
                hardware,
                apis,
                i18n=i18n,
            )
            _collect_runtime()
            _mem_snapshot("app.lazy.updater_created", enabled=_DEBUG, collect=True)
            return True
        return False

    def _create_launcher(self, screen_manager, hardware, apis, i18n):
        from apps.launcher_app import LauncherApp

        self._apps["launcher"] = LauncherApp(screen_manager, hardware, apis, i18n=i18n)
        _collect_runtime()
        _mem_snapshot("app.lazy.launcher_created", enabled=_DEBUG, collect=True)

    def _create_scale(self, screen_manager, hardware, apis, i18n):
        from apps.scale_app import ScaleApp

        self._apps["scale_app"] = ScaleApp(screen_manager, hardware, apis, i18n=i18n)
        _collect_runtime()
        _mem_snapshot("app.lazy.scale_created", enabled=_DEBUG, collect=True)

    def _create_malt(self, screen_manager, hardware, apis, i18n):
        from apps.malt_app import GrainAssistantApp

        self._apps["malt_app"] = GrainAssistantApp(screen_manager, hardware, apis, i18n=i18n)
        _collect_runtime()
        _mem_snapshot("app.lazy.malt_created", enabled=_DEBUG, collect=True)

    def _create_hop(self, screen_manager, hardware, apis, i18n):
        from apps.hop_app import HopAssistantApp

        self._apps["hop_app"] = HopAssistantApp(
            screen_manager,
            hardware,
            apis,
            i18n=i18n,
        )
        _collect_runtime()
        _mem_snapshot("app.lazy.hop_created", enabled=_DEBUG, collect=True)

    def _create_keg(self, screen_manager, hardware, apis, i18n):
        from apps.keg_filler_app import KegFillerApp

        self._apps["keg_filler_app"] = KegFillerApp(screen_manager, hardware, apis, i18n=i18n)
        _collect_runtime()
        _mem_snapshot("app.lazy.keg_created", enabled=_DEBUG, collect=True)

    def _switch_to(self, app_id):
        if app_id == self._active_app_id:
            return
        old = self._active_app_id
        current_app = self._apps[old]
        screen_manager = current_app.screen_manager
        hardware = current_app.hardware
        current_i18n = current_app.i18n
        target_app_id = app_id
        target_exists = app_id in self._apps
        if not target_exists and not self._is_known_app_id(app_id):
            target_app_id = "launcher"
            target_exists = target_app_id in self._apps
        _mem_snapshot("switch.before_old_exit", enabled=_DEBUG, collect=True)
        try:
            current_app.on_exit()
        except Exception as exc:
            if _DEBUG:
                try:
                    print("[AppManager] app exit error: {}".format(exc))
                except Exception:
                    pass
        finally:
            release_runtime_state = getattr(current_app, "release_runtime_state", None)
            if release_runtime_state:
                try:
                    release_runtime_state()
                except Exception:
                    pass
        _collect_runtime()
        _mem_snapshot("switch.after_old_exit", enabled=_DEBUG, collect=True)
        self._release_app_screen_refs()
        if old == "keg_filler_app":
            self._evict_app(old)
            # _evict_app() drops its own local reference, but current_app
            # still keeps the heavy KegFillerApp alive until _switch_to()
            # returns. Release it before LVGL and the next app allocate.
            current_app = None
            # _evict_app() collected while current_app was still alive. Run
            # another collection now that the last app reference is gone,
            # before the transition screen can allocate LVGL objects.
            _collect_runtime(cycles=2)
            _mem_snapshot("switch.after_evict", enabled=_DEBUG, collect=False)
        self._memory_cleanup_before_enter(target_app_id)
        _collect_runtime()
        _mem_snapshot("switch.after_gc", enabled=_DEBUG, collect=False)
        if not target_exists and not self._ensure_app(
            target_app_id,
            screen_manager,
            hardware,
            self._apis,
            current_i18n,
        ):
            target_app_id = "launcher"
            if target_app_id not in self._apps:
                self._ensure_app(
                    target_app_id,
                    screen_manager,
                    hardware,
                    self._apis,
                    current_i18n,
                )
        _collect_runtime()
        _mem_snapshot("switch.after_ensure", enabled=_DEBUG, collect=True)
        try:
            import config
            if getattr(config, "DEBUG", False):
                print("[MEM] switch {}->{} free={}".format(old, target_app_id, gc.mem_free()))
        except Exception:
            pass
        self._active_app_id = target_app_id
        _mem_snapshot("switch.before_new_enter", enabled=_DEBUG, collect=False)
        self._apps[self._active_app_id].on_enter()
        release_cleanup = getattr(self._screen_manager, "release_cleanup_screen", None)
        if release_cleanup:
            release_cleanup()
        _collect_runtime()
        _mem_snapshot("switch.after_new_enter", enabled=_DEBUG, collect=True)

    @staticmethod
    def _is_known_app_id(app_id):
        return app_id in (
            "launcher",
            "scale_app",
            "malt_app",
            "hop_app",
            "keg_filler_app",
            "settings_app",
            CALIBRATION_WIZARD_APP_ID,
            "updater_app",
        )

    def _release_app_screen_refs(self):
        for app in self._apps.values():
            release_refs = getattr(app, "release_screen_refs", None)
            if release_refs:
                try:
                    release_refs()
                except Exception:
                    pass

    def _evict_app(self, app_id):
        """Drop a heavy lazy app and its module after its exit lifecycle."""
        app = self._apps.pop(app_id, None)
        if app is None:
            return
        module_name = getattr(app.__class__, "__module__", None)
        if module_name and module_name.startswith("apps."):
            module = sys.modules.pop(module_name, None)
            if module is not None:
                package_name, _, child_name = module_name.rpartition(".")
                package = sys.modules.get(package_name)
                if package is not None:
                    try:
                        # Importing apps.keg_filler_app also stores the module
                        # as apps.keg_filler_app. Remove that second reference
                        # or the module code remains reachable after pop().
                        if getattr(package, child_name, None) is module:
                            delattr(package, child_name)
                    except Exception:
                        pass
        del app
        _collect_runtime(cycles=2)

    def _memory_cleanup_before_enter(self, app_id):
        cleanup = getattr(self._screen_manager, "memory_cleanup", None)
        if cleanup:
            cleanup(
                loading_message=self._loading_message_for(app_id),
                loading_color=self._loading_color_for(app_id),
            )

    def _loading_message_for(self, app_id):
        if app_id == "hop_app":
            if self._i18n:
                try:
                    return self._i18n.t("recipe.loading_recipes")
                except Exception:
                    pass
            return "Loading recipes..."
        app_key_by_id = {
            "scale_app": "launcher.scale",
            "malt_app": "launcher.malt",
            "hop_app": "launcher.hop",
            "keg_filler_app": "launcher.keg",
            "settings_app": "launcher.settings",
            CALIBRATION_WIZARD_APP_ID: "scale_calibration.title",
            "updater_app": "updater.title",
        }
        fallback_by_id = {
            "launcher": "Launcher",
            "scale_app": "Scale",
            "malt_app": "Malt",
            "hop_app": "Hop",
            "keg_filler_app": "Keg",
            "settings_app": "Settings",
            CALIBRATION_WIZARD_APP_ID: "Calibration",
            "updater_app": "Updater",
        }
        app_name = fallback_by_id.get(app_id, app_id)
        key = app_key_by_id.get(app_id)
        if self._i18n and key:
            try:
                app_name = self._i18n.t(key)
            except Exception:
                pass
        if self._i18n:
            try:
                return self._i18n.t("common.loading_app", app_name)
            except Exception:
                pass
        return "Loading {}".format(app_name)

    @staticmethod
    def _loading_color_for(app_id):
        return {
            "scale_app": 0x00A8E8,
            "malt_app": 0xD4840A,
            "hop_app": 0x388E3C,
            "keg_filler_app": 0x607D8B,
            "settings_app": 0x7E57C2,
            CALIBRATION_WIZARD_APP_ID: 0x00897B,
            "updater_app": 0x1565C0,
        }.get(app_id, 0x333333)

    def tick(self):
        next_app = self._apps[self._active_app_id].tick()
        if next_app:
            self._switch_to(next_app)
