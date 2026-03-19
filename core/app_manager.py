"""
App manager with persistent one-time app instances.
"""

import gc

from apps.launcher_app import LauncherApp
from apps.scale import ScaleApp
from apps.grain_assistant import GrainAssistantApp
from apps.hop_assistant import HopAssistantApp
from apps.keg_filler import KegFillerApp
from apps.settings import SettingsApp


class AppManager:
    def __init__(self, screen_manager, hardware, apis, i18n=None):
        self._apps = {
            "launcher": LauncherApp(screen_manager, hardware, apis, i18n=i18n),
            "scale": ScaleApp(screen_manager, hardware, apis, i18n=i18n),
            "grain_assistant": GrainAssistantApp(screen_manager, hardware, apis, i18n=i18n),
            "hop_assistant": HopAssistantApp(screen_manager, hardware, apis, i18n=i18n),
            "keg_filler": KegFillerApp(screen_manager, hardware, apis, i18n=i18n),
            "settings": SettingsApp(screen_manager, hardware, apis, i18n=i18n),
        }
        self._active_app_id = "launcher"
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
