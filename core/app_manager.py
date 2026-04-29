"""
App manager with persistent one-time app instances.
"""

import gc
import os

from apps.launcher_app import LauncherApp
from apps.scale_app import ScaleApp
from apps.malt_app import GrainAssistantApp
from apps.hop_app import HopAssistantApp
from apps.keg_filler_app import KegFillerApp
from memory_debug import snapshot as mem_snapshot

try:
    import config
    _DEBUG = getattr(config, "DEBUG", False)
except Exception:
    _DEBUG = False


CALIBRATION_FILE = "scale_calibration.json"
CALIBRATION_WIZARD_APP_ID = "scale_calibration_wizard_app"


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
        mem_snapshot("app.init.start", enabled=_DEBUG, collect=True)
        self._apis = apis
        self._apps = {}
        self._apps["launcher"] = LauncherApp(screen_manager, hardware, apis, i18n=i18n)
        mem_snapshot("app.after_launcher", enabled=_DEBUG, collect=True)
        self._apps["scale_app"] = ScaleApp(screen_manager, hardware, apis, i18n=i18n)
        mem_snapshot("app.after_scale", enabled=_DEBUG, collect=True)
        self._apps["malt_app"] = GrainAssistantApp(screen_manager, hardware, apis, i18n=i18n)
        mem_snapshot("app.after_malt", enabled=_DEBUG, collect=True)
        self._apps["hop_app"] = HopAssistantApp(screen_manager, hardware, apis, i18n=i18n)
        mem_snapshot("app.after_hop", enabled=_DEBUG, collect=True)
        self._apps["keg_filler_app"] = KegFillerApp(screen_manager, hardware, apis, i18n=i18n)
        mem_snapshot("app.after_keg", enabled=_DEBUG, collect=True)
        self._active_app_id = _initial_app_id(initial_app_id=initial_app_id)
        self._ensure_app(self._active_app_id, screen_manager, hardware, apis, i18n)
        mem_snapshot("app.after_initial_app", enabled=_DEBUG, collect=True)
        self._apps[self._active_app_id].on_enter()
        mem_snapshot("app.after_on_enter", enabled=_DEBUG, collect=True)

    def _ensure_app(self, app_id, screen_manager=None, hardware=None, apis=None, i18n=None):
        if app_id in self._apps:
            return True
        if app_id == "settings_app":
            from apps.settings_app import SettingsApp

            self._apps[app_id] = SettingsApp(
                screen_manager,
                hardware,
                apis,
                i18n=i18n,
            )
            mem_snapshot("app.lazy.settings_created", enabled=_DEBUG, collect=True)
            return True
        if app_id == CALIBRATION_WIZARD_APP_ID:
            from apps.scale_calibration_wizard_app import ScaleCalibrationWizardApp

            self._apps[app_id] = ScaleCalibrationWizardApp(
                screen_manager,
                hardware,
                apis,
                i18n=i18n,
            )
            mem_snapshot("app.lazy.calibration_created", enabled=_DEBUG, collect=True)
            return True
        return False

    def _switch_to(self, app_id):
        if not self._ensure_app(
            app_id,
            self._apps[self._active_app_id].screen_manager,
            self._apps[self._active_app_id].hardware,
            self._apis,
            self._apps[self._active_app_id].i18n,
        ):
            app_id = "launcher"
        if app_id == self._active_app_id:
            return
        old = self._active_app_id
        self._apps[old].on_exit()
        gc.collect()
        gc.collect()
        try:
            import config
            if getattr(config, "DEBUG", False):
                print("[MEM] switch {}->{} free={}".format(old, app_id, gc.mem_free()))
        except Exception:
            pass
        self._active_app_id = app_id
        self._apps[self._active_app_id].on_enter()

    def tick(self):
        next_app = self._apps[self._active_app_id].tick()
        if next_app:
            self._switch_to(next_app)
