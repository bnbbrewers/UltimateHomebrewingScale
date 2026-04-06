"""
Ultimate Homebrewing Scale - persistent memory-safe runtime.
"""

import gc
import time
import M5
from M5 import *
import m5ui
import lvgl as lv

from core import ScreenManager, HardwareManager, AppManager, ApiFactory
from memory_debug import snapshot as mem_snapshot

try:
    import config
    DEBUG = getattr(config, "DEBUG", False)
except Exception:
    config = None
    DEBUG = False


def _load_i18n():
    try:
        from i18n import I18n

        language = getattr(config, "LANGUAGE", "en")
        return I18n(language)
    except Exception:
        return None


def main():
    M5.begin()
    m5ui.init()
    Speaker.begin()
    gc.collect()
    mem_snapshot("boot.start", enabled=DEBUG)

 

    i18n_instance = _load_i18n()
    hardware = HardwareManager.get_instance()
    apis = ApiFactory().as_dict()

    screen_manager = ScreenManager(i18n=i18n_instance)
    app_manager = AppManager(
        screen_manager=screen_manager,
        hardware=hardware,
        apis=apis,
        i18n=i18n_instance,
    )
    mem_snapshot("boot.ui_ready", enabled=DEBUG, collect=True)

    # Warmup kept after UI init (historically stable behavior on this project).
    brewing_api = apis.get("brewing")
    if brewing_api is not None:
        try:
            mem_snapshot("boot.pre_warmup", enabled=DEBUG, collect=True)
            brewing_api.warmup()
            mem_snapshot("boot.post_warmup", enabled=DEBUG, collect=True)
        except Exception as e:
            if DEBUG:
                print("[BOOT] warmup failed:", e)

    while True:
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
