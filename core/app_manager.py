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
from apps.settings_app import SettingsApp
from apps.scale_calibration_wizard_app import ScaleCalibrationWizardApp


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


def _initial_app_id():
    if _file_exists(CALIBRATION_FILE):
        return "launcher"
    return CALIBRATION_WIZARD_APP_ID


class AppManager:
    def __init__(self, screen_manager, hardware, apis, i18n=None):
        self._apis = apis
        self._apps = {
            "launcher": LauncherApp(screen_manager, hardware, apis, i18n=i18n),
            "scale_app": ScaleApp(screen_manager, hardware, apis, i18n=i18n),
            "malt_app": GrainAssistantApp(screen_manager, hardware, apis, i18n=i18n),
            "hop_app": HopAssistantApp(screen_manager, hardware, apis, i18n=i18n),
            "keg_filler_app": KegFillerApp(screen_manager, hardware, apis, i18n=i18n),
            "settings_app": SettingsApp(screen_manager, hardware, apis, i18n=i18n),
            CALIBRATION_WIZARD_APP_ID: ScaleCalibrationWizardApp(
                screen_manager,
                hardware,
                apis,
                i18n=i18n,
            ),
        }
        self._active_app_id = _initial_app_id()
        self._apps[self._active_app_id].on_enter()

    def _switch_to(self, app_id):
        if app_id not in self._apps:
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
