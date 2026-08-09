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
        if bool(getattr(config, "UPDATE_ON_BOOT", False)):
            return True
    except Exception:
        pass
    try:
        from storage import config_registry

        return config_registry.is_update_requested()
    except Exception:
        return False


def _startup_config_ready():
    config_exists = _file_exists("config.py")
    if DEBUG:
        try:
            print(
                "[BOOTCFG] cwd_config_exists={} config_imported={} config_file={}".format(
                    config_exists,
                    config is not None,
                    getattr(config, "__file__", "?") if config is not None else "",
                )
            )
        except Exception:
            pass
    if not config_exists:
        if DEBUG:
            try:
                print("[BOOTCFG] startup_ready=False reason=missing_relative_config")
            except Exception:
                pass
        return False
    try:
        from storage import config_registry

        try:
            report = config_registry.wifi_credentials_report()
            if DEBUG:
                print(
                    "[WIFICFG] nvs_ssid={} config_path={} config_exists={} config_ssid={} error={}".format(
                        report.get("nvs_ssid"),
                        report.get("config_path"),
                        report.get("config_exists"),
                        report.get("config_ssid"),
                        report.get("error", ""),
                    )
                )
        except Exception as e:
            if DEBUG:
                print("[WIFICFG] report_error={}".format(e))
        ready = config_registry.wifi_credentials_ready()
        if DEBUG:
            print("[BOOTCFG] startup_ready={} reason=wifi_credentials_ready".format(ready))
        return ready
    except Exception as e:
        if DEBUG:
            try:
                print("[BOOTCFG] startup_ready=False reason=config_registry_error {}".format(e))
            except Exception:
                pass
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
    api_factory = ApiFactory(wifi_device=hardware.wifi)

    initial_app_id = None
    initial_screen_id = None
    startup_ready = _startup_config_ready()
    update_requested = startup_ready and _update_requested()
    if update_requested:
        initial_app_id = "updater_app"
        initial_screen_id = "simple_message"
    elif not startup_ready:
        initial_app_id = "settings_app"
    elif startup_ready:
        # Keep the normal configured path compatible with the alpha runtime:
        # Wi-Fi warms up in the background while the launcher is available,
        # leaving the API workflow to use an already-settled interface.
        hardware.wifi.request_connection()
        # The connector is deliberately warmed while the C heap is still
        # healthy. Its import used to happen at boot; deferring it until the
        # first Malt/Hop transition leaves too little contiguous heap for TLS.
        api_factory.get("brewing")
    apis = api_factory.as_dict()
    mem_snapshot("boot.after_api_factory", enabled=DEBUG, collect=True)
    if DEBUG:
        try:
            print("[BOOTCFG] initial_app_id={}".format(initial_app_id))
        except Exception:
            pass
    screen_manager = ScreenManager(i18n=i18n_instance, initial_screen_id=initial_screen_id)
    mem_snapshot("boot.after_screen_manager", enabled=DEBUG, collect=True)
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
        hardware.tick()
        app_manager.tick()
        lv.task_handler()
        time.sleep_ms(10)

try:
    main()
except KeyboardInterrupt:
    if DEBUG:
        print("Stopped by user")
