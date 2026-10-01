"""
App manager with persistent one-time app instances.
"""

import gc
import os
import sys

import app_registry
import runtime_debug

CALIBRATION_FILE = "scale_calibration.json"
CALIBRATION_WIZARD_APP_ID = app_registry.CALIBRATION_WIZARD
# Imported by whichever recipe app runs, and by neither one afterwards. It is
# evicted with them so the base class does not stay resident for a session
# that never opens Malt or Hop again.
_COMPANION_MODULES = ("apps.recipe_app",)


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
        return app_registry.LAUNCHER
    return CALIBRATION_WIZARD_APP_ID


class AppManager:
    def __init__(self, screen_manager, hardware, apis, i18n=None, initial_app_id=None):
        runtime_debug.collect()
        runtime_debug.snapshot("app.init.start", collect=True)
        self._screen_manager = screen_manager
        self._i18n = i18n
        self._apis = apis
        self._apps = {}
        # Only the active app is created during boot: the main loop needs one
        # app to tick, but every other app stays lazy until the launcher or
        # startup flow selects it. This keeps C/Python heap pressure low.
        self._active_app_id = _initial_app_id(initial_app_id=initial_app_id)
        self._ensure_app(self._active_app_id, screen_manager, hardware, apis, i18n)
        runtime_debug.collect()
        runtime_debug.snapshot("app.after_initial_app", collect=True)
        self._apps[self._active_app_id].on_enter()
        runtime_debug.collect()
        runtime_debug.snapshot("app.after_on_enter", collect=True)

    def active_app_id(self):
        """Read-only accessor used by standby to inhibit on specific apps."""
        return self._active_app_id

    def standby_inhibited(self):
        """True while the active app must not be interrupted by deep sleep.

        Two reasons: the app is inherently uninterruptible (declared in the
        registry), or it is in the middle of a physical operation and says so
        through inhibits_standby(). The keg filler uses the second form, since
        only the fill itself must hold the device awake.
        """
        app_id = self._active_app_id
        if app_registry.inhibits_standby(app_id):
            return True
        app = self._apps.get(app_id)
        asks = getattr(app, "inhibits_standby", None)
        if asks is None:
            return False
        try:
            return bool(asks())
        except Exception:
            return False

    def _ensure_app(self, app_id, screen_manager=None, hardware=None, apis=None, i18n=None):
        if app_id in self._apps:
            return True
        app_class = app_registry.load_class(app_id)
        if app_class is None:
            return False
        self._apps[app_id] = app_class(screen_manager, hardware, apis, i18n=i18n)
        runtime_debug.collect()
        runtime_debug.snapshot("app.lazy.{}_created".format(app_id), collect=True)
        return True

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
        if not target_exists and not app_registry.is_known(app_id):
            target_app_id = app_registry.LAUNCHER
            target_exists = target_app_id in self._apps
        runtime_debug.snapshot("switch.before_old_exit", collect=True)
        try:
            current_app.on_exit()
        except Exception as exc:
            runtime_debug.log("[AppManager] app exit error: {}", exc)
        finally:
            release_runtime_state = getattr(current_app, "release_runtime_state", None)
            if release_runtime_state:
                try:
                    release_runtime_state()
                except Exception:
                    pass
        runtime_debug.collect()
        runtime_debug.snapshot("switch.after_old_exit", collect=True)
        self._release_app_screen_refs()

        self._evict_non_launcher_apps()
        current_app = None
        runtime_debug.collect(cycles=2)
        runtime_debug.snapshot("switch.after_evict")
        target_exists = target_app_id in self._apps
        self._memory_cleanup_before_enter(target_app_id)
        runtime_debug.collect()
        runtime_debug.snapshot("switch.after_gc")
        if not target_exists and not self._ensure_app(
            target_app_id,
            screen_manager,
            hardware,
            self._apis,
            current_i18n,
        ):
            target_app_id = app_registry.LAUNCHER
            if target_app_id not in self._apps:
                self._ensure_app(
                    target_app_id,
                    screen_manager,
                    hardware,
                    self._apis,
                    current_i18n,
                )
        runtime_debug.collect()
        runtime_debug.snapshot("switch.after_ensure", collect=True)
        runtime_debug.log(
            "[MEM] switch {}->{} free={}", old, target_app_id, runtime_debug.mem_free()
        )
        self._active_app_id = target_app_id
        runtime_debug.snapshot("switch.before_new_enter")
        self._apps[self._active_app_id].on_enter()
        release_cleanup = getattr(self._screen_manager, "release_cleanup_screen", None)
        if release_cleanup:
            release_cleanup()
        # Do not run GC after entering the new screen. On the Dial, collecting
        # here can finalize LVGL wrappers while the m5ui task handler is being
        # serviced, causing a native allocation failure in m5ui/port.py. The
        # transition cleanup above already collects before the new app enters;
        # the next loop iteration can service LVGL without this re-entrant GC.
        runtime_debug.snapshot("switch.after_new_enter")

    def _release_app_screen_refs(self):
        for app in self._apps.values():
            release_refs = getattr(app, "release_screen_refs", None)
            if release_refs:
                try:
                    release_refs()
                except Exception:
                    pass

    def _evict_non_launcher_apps(self):
        for app_id in list(self._apps.keys()):
            if app_id == app_registry.LAUNCHER:
                continue
            app = self._apps.pop(app_id, None)
            if app is None:
                continue
            # Read the module off the instance rather than off the registry:
            # that is what makes the eviction work for an app the registry
            # does not know, and it cannot drift from where the class came
            # from.
            module_name = getattr(app.__class__, "__module__", None)
            if module_name and (
                module_name.startswith("apps.")
                or module_name.startswith("updater.")
            ):
                _evict_module(module_name)
            del app
        for module_name in _COMPANION_MODULES:
            _evict_module(module_name)

    def _memory_cleanup_before_enter(self, app_id):
        cleanup = getattr(self._screen_manager, "memory_cleanup", None)
        if cleanup:
            cleanup(
                loading_message=self._loading_message_for(app_id),
                loading_color=self._loading_color_for(app_id),
            )

    def _translate(self, key, *args):
        if not self._i18n or not key:
            return None
        try:
            return self._i18n.t(key, *args)
        except Exception:
            return None

    def _loading_message_for(self, app_id):
        spec = app_registry.spec(app_id) or {}
        # An app whose wait is about something other than itself carries its
        # own line: Hop downloads recipes before it can show anything.
        override = self._translate(spec.get("loading_i18n"))
        if override:
            return override
        if spec.get("loading_label"):
            return spec["loading_label"]

        app_name = self._translate(spec.get("i18n")) or spec.get("label", app_id)
        return self._translate("common.loading_app", app_name) or "Loading {}".format(app_name)

    @staticmethod
    def _loading_color_for(app_id):
        return app_registry.color(app_id)

    def tick(self):
        next_app = self._apps[self._active_app_id].tick()
        if next_app:
            self._switch_to(next_app)
