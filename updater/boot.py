"""Minimal boot-time updater.

This module deliberately avoids importing the application, UI managers,
hardware drivers, or API connectors. It is loaded before the normal runtime so
the update can run with the largest possible free heap.
"""

import time


_NVS_NAMESPACE = "uhs"
_NVS_UPDATE_KEY = "update"


def _open_nvs():
    import esp32

    return esp32.NVS(_NVS_NAMESPACE)


def _read_update_flag(nvs):
    if hasattr(nvs, "get_i32"):
        try:
            return int(nvs.get_i32(_NVS_UPDATE_KEY))
        except Exception:
            pass

    if hasattr(nvs, "get_blob"):
        try:
            buf = bytearray(8)
            size = nvs.get_blob(_NVS_UPDATE_KEY, buf)
            if isinstance(size, int) and size > 0:
                raw = bytes(buf[:size])
            else:
                raw = bytes(buf).split(b"\x00", 1)[0]
            if not raw:
                return 0
            try:
                return int(raw.decode("utf-8"))
            except Exception:
                return int(raw[0])
        except Exception:
            pass

    return 0


def _write_update_flag(nvs, value):
    if hasattr(nvs, "set_i32"):
        nvs.set_i32(_NVS_UPDATE_KEY, int(value))
        return
    if hasattr(nvs, "set_blob"):
        nvs.set_blob(_NVS_UPDATE_KEY, str(int(value)))
        return
    raise OSError("NVS integer write API unavailable")


def is_update_requested(nvs=None):
    try:
        nvs = nvs or _open_nvs()
        return _read_update_flag(nvs) == 1
    except Exception:
        return False


def set_update_requested(requested, nvs=None):
    nvs = nvs or _open_nvs()
    _write_update_flag(nvs, 1 if requested else 0)
    nvs.commit()


def _load_wifi_credentials():
    try:
        import esp32

        nvs = esp32.NVS("uiflow")
        ssid = nvs.get_str("ssid0") or ""
        password = nvs.get_str("pswd0") or ""
        if ssid:
            return ssid, password
    except Exception:
        pass

    try:
        import config

        ssid = getattr(config, "WIFI_SSID", "") or ""
        password = (
            getattr(config, "WIFI_PASSWORD", "")
            or getattr(config, "WIFI_PSWD", "")
            or ""
        )
        return ssid, password
    except Exception:
        return "", ""


class MinimalWifi:
    """Small blocking Wi-Fi adapter used only by the boot updater."""

    def __init__(self, wlan=None):
        self._wlan = wlan

    def ensure_connected(self, timeout_s=25):
        if self._wlan is None:
            import network

            self._wlan = network.WLAN(network.STA_IF)
        if self._wlan.isconnected():
            return True

        ssid, password = _load_wifi_credentials()
        if not ssid:
            raise RuntimeError("missing WiFi SSID")
        if not self._wlan.active():
            self._wlan.active(True)
        self._wlan.connect(ssid, password)

        deadline = time.ticks_add(time.ticks_ms(), int(timeout_s * 1000))
        while not self._wlan.isconnected():
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                return False
            time.sleep_ms(200)
        time.sleep_ms(300)
        return True


def _channel():
    try:
        import config

        value = getattr(config, "UPDATE_CHANNEL", "stable")
    except Exception:
        value = "stable"
    return "prerelease" if str(value or "").strip().lower() == "prerelease" else "stable"


def _progress(event):
    try:
        stage = event.get("stage", "update")
        message = event.get("message", "")
        detail = event.get("detail", "")
        if detail:
            print("[updater] {}: {} ({})".format(stage, message, detail))
        else:
            print("[updater] {}: {}".format(stage, message))
    except Exception:
        pass


def updater_title(version_detail=""):
    detail = str(version_detail or "").strip()
    return "Updater\n{}".format(detail) if detail else "Updater"


class _DialProgress:
    """Optional progress renderer loaded only in the updater boot path."""

    def __init__(self):
        self._screen = None
        self._m5 = None
        self._lv = None
        try:
            import M5
            import lvgl as lv
            import m5ui
            from ui.updater_screen import UpdaterScreen

            M5.begin()
            m5ui.init()
            self._screen = UpdaterScreen()
            self._screen.root().screen_load()
            self._screen.configure(
                title="Updater",
                title_bg_color=0x1565C0,
            )
            self._m5 = M5
            self._lv = lv
        except Exception as error:
            self._screen = None
            try:
                print("[updater] progress UI unavailable: {}".format(error))
            except Exception:
                pass

    def callback(self, event):
        _progress(event)
        if self._screen is None:
            return
        try:
            message = event.get("message", "")
            detail = event.get("detail", "")
            if event.get("stage") == "version" and detail:
                self._screen.set_title(updater_title(detail))
            self._screen.set_status(message, detail)
            total = event.get("total", 0)
            if total:
                self._screen.set_progress(event.get("percent", 0))
            elif event.get("stage") in ("wifi", "release", "manifest", "extract"):
                self._screen.set_progress(0)
            self._m5.update()
            self._lv.task_handler()
        except Exception:
            pass

    def show_error(self, error):
        if self._screen is None:
            return
        try:
            self._screen.show_error(str(error))
            self._m5.update()
            self._lv.task_handler()
        except Exception:
            pass


def _reset():
    try:
        import machine

        machine.reset()
    except Exception:
        try:
            import M5

            M5.Power.reset()
        except Exception:
            pass


def run_update_boot(
    nvs=None,
    update_fn=None,
    reset_fn=None,
    wifi=None,
    channel=None,
    progress_callback=None,
):
    """Run the update and reset only after a successful installation.

    Dependencies are injectable so the flag lifecycle can be tested on a host
    without importing MicroPython modules.
    """
    if update_fn is None:
        from .workflow import update as update_fn
    if reset_fn is None:
        reset_fn = _reset
    if wifi is None:
        wifi = MinimalWifi()
    if channel is None:
        channel = _channel()
    display = None
    if progress_callback is None:
        display = _DialProgress()
        progress_callback = display.callback

    try:
        result = update_fn(
            channel=channel,
            progress_callback=progress_callback,
            wifi_device=wifi,
            ensure_wifi=True,
        )
        more_updates = isinstance(result, dict) and result.get("more_updates", False)
        if not more_updates:
            set_update_requested(False, nvs=nvs)
        reset_fn()
        return True
    except Exception as error:
        if display is not None:
            display.show_error(error)
        try:
            print("[updater] failed: {}".format(error))
        except Exception:
            pass
        return False
