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


def is_update_requested(nvs=None):
    try:
        nvs = nvs or _open_nvs()
        if hasattr(nvs, "get_i32"):
            return int(nvs.get_i32(_NVS_UPDATE_KEY)) == 1
        return False
    except Exception:
        return False


def set_update_requested(requested, nvs=None):
    nvs = nvs or _open_nvs()
    if not hasattr(nvs, "set_i32"):
        raise OSError("NVS integer write API unavailable")
    nvs.set_i32(_NVS_UPDATE_KEY, 1 if requested else 0)
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
    if progress_callback is None:
        progress_callback = _progress

    try:
        update_fn(
            channel=channel,
            progress_callback=progress_callback,
            wifi_device=wifi,
            ensure_wifi=True,
        )
        set_update_requested(False, nvs=nvs)
        reset_fn()
        return True
    except Exception as error:
        try:
            print("[updater] failed: {}".format(error))
        except Exception:
            pass
        return False
