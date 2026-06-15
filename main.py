"""
Ultimate Homebrewing Scale - persistent memory-safe runtime.
"""

import gc
import os
import time
import M5
from M5 import *
import m5ui
import lvgl as lv


def _file_exists(path):
    try:
        return os.path.exists(path)
    except AttributeError:
        try:
            os.stat(path)
            return True
        except OSError:
            return False


try:
    import config
    DEBUG = getattr(config, "DEBUG", False)
except Exception:
    config = None
    DEBUG = False

if DEBUG:
    from memory_debug import snapshot as mem_snapshot
else:
    def mem_snapshot(*args, **kwargs):
        return None

from core import ScreenManager, HardwareManager, AppManager, ApiFactory

_RUNNING = True


def _load_i18n():
    try:
        from i18n import I18n

        language = getattr(config, "LANGUAGE", "en")
        return I18n(language)
    except Exception:
        return None


def _update_requested():
    try:
        from storage import config_registry

        return config_registry.is_update_requested()
    except Exception:
        return False


def _startup_config_ready():
    if not _file_exists("config.py"):
        return False
    try:
        from storage import config_registry

        return config_registry.wifi_credentials_ready()
    except Exception:
        return False


def request_stop():
    global _RUNNING
    _RUNNING = False


def main():
    global _RUNNING
    _RUNNING = True
    M5.begin()
    mem_snapshot("boot.after_m5_begin", enabled=DEBUG, collect=True)
    m5ui.init()
    mem_snapshot("boot.after_m5ui_init", enabled=DEBUG, collect=True)
    Speaker.begin()
    mem_snapshot("boot.after_speaker", enabled=DEBUG, collect=True)
    gc.collect()
    mem_snapshot("boot.start", enabled=DEBUG)

    i18n_instance = _load_i18n()
    mem_snapshot("boot.after_i18n", enabled=DEBUG, collect=True)
    hardware = HardwareManager.get_instance()
    mem_snapshot("boot.after_hardware", enabled=DEBUG, collect=True)
    apis = ApiFactory().as_dict()
    mem_snapshot("boot.after_api_factory", enabled=DEBUG, collect=True)

    screen_manager = ScreenManager(i18n=i18n_instance)
    mem_snapshot("boot.after_screen_manager", enabled=DEBUG, collect=True)
    initial_app_id = None
    startup_ready = _startup_config_ready()
    if startup_ready and _update_requested():
        initial_app_id = "updater_app"
    elif not startup_ready:
        initial_app_id = "settings_app"
    app_manager = AppManager(
        screen_manager=screen_manager,
        hardware=hardware,
        apis=apis,
        i18n=i18n_instance,
        initial_app_id=initial_app_id,
    )
    mem_snapshot("boot.after_app_manager", enabled=DEBUG, collect=True)
    mem_snapshot("boot.ui_ready", enabled=DEBUG, collect=True)
    while _RUNNING:
        M5.update()
        app_manager.tick()
        hardware.tick()
        lv.task_handler()
        time.sleep_ms(10)

try:
    main()
except KeyboardInterrupt:
    if DEBUG:
        print("Stopped by user")
