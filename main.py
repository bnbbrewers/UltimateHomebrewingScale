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

_RUNNING = True


def _load_i18n():
    try:
        from i18n import I18n

        language = getattr(config, "LANGUAGE", "en")
        return I18n(language)
    except Exception:
        return None


def request_stop():
    global _RUNNING
    _RUNNING = False


def _maintenance_mode_requested(hold_ms=1200):
    """
    Hold BtnA during boot to skip launching the main app loop.
    This keeps REPL available for maintenance tasks (installer/update).
    """
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < hold_ms:
        M5.update()
        if not M5.BtnA.isPressed():
            return False
        time.sleep_ms(30)
    return True


def main():
    global _RUNNING
    _RUNNING = True
    M5.begin()
    m5ui.init()
    Speaker.begin()
    gc.collect()
    mem_snapshot("boot.start", enabled=DEBUG)

    if _maintenance_mode_requested():
        print("[main] Maintenance mode: app startup skipped (BtnA held).")
        return

 

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
