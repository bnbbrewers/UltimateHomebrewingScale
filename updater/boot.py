"""Minimal boot-time updater.

This module deliberately avoids importing the application, UI managers,
hardware drivers, or API connectors. It is loaded before the normal runtime so
the update can run with the largest possible free heap.
"""

import time

import nvs_store


def is_update_requested(nvs=None):
    return nvs_store.read_update_flag(nvs=nvs)


def set_update_requested(requested, nvs=None):
    nvs_store.write_update_flag(requested, nvs=nvs)


def _load_wifi_credentials():
    """NVS first, then config.py, exactly like devices.wifi does."""
    ssid, password = nvs_store.read_wifi_credentials()
    if ssid:
        return ssid, password

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

    def can_wait_ok(self):
        return self._screen is not None

    def wait_ok(self):
        """Block until the physical button is pressed and released."""
        button = self._m5.BtnA
        pressed = False
        while True:
            self._m5.update()
            self._lv.task_handler()
            if button.isPressed():
                pressed = True
            elif pressed:
                return
            time.sleep_ms(20)


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
    wait_ok_fn=None,
):
    """Run the update and reset only after a successful installation.

    On a failure, OK restarts the device. It drops the update request when the
    failure came before the install, so the application boots; once files are
    being replaced, the request stays set and the restart retries the update.

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
    if wait_ok_fn is None and display is not None and display.can_wait_ok():
        wait_ok_fn = display.wait_ok

    installing = [False]

    def track_progress(event):
        if event.get("stage") == "extract":
            installing[0] = True
        progress_callback(event)

    try:
        result = update_fn(
            channel=channel,
            progress_callback=track_progress,
            wifi_device=wifi,
            ensure_wifi=True,
        )
        # A release ships the complete runtime, so one pass always lands on the
        # newest version: there is never a second step to keep the flag for.
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
        if wait_ok_fn is not None:
            wait_ok_fn()
            if not installing[0]:
                set_update_requested(False, nvs=nvs)
            reset_fn()
        return False
