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

try:
    import config
    DEBUG = getattr(config, "DEBUG", False)
except Exception:
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
    gc.collect()

 

    i18n_instance = _load_i18n()
    screen_manager = ScreenManager(i18n=i18n_instance)
    hardware = HardwareManager.get_instance()
    apis = ApiFactory().as_dict()

    app_manager = AppManager(
        screen_manager=screen_manager,
        hardware=hardware,
        apis=apis,
        i18n=i18n_instance,
    )
    # TLS warmup: open the persistent TLS socket now, while the IDF C-heap
    # is still contiguous (before LVGL icon bitmaps fragment it).
    # Subsequent API calls reuse this socket via HTTP/1.1 keep-alive,
    # avoiding a new TLS handshake (and its ~40 KB X.509 allocation).
    brewing_api = apis.get("brewing")
    if brewing_api is not None:
        try:
            brewing_api.warmup()
        except Exception as e:
            if DEBUG:
                print("[BOOT] TLS warmup failed:", e)
    gc.collect()

    while True:
        M5.update()
        app_manager.tick()
        hardware.tick()
        lv.task_handler()
        #time.sleep_ms(30)

try:
    main()
except KeyboardInterrupt:
    if DEBUG:
        print("Stopped by user")
