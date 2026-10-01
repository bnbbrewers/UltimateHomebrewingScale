"""
Hidden boot app: connect to the saved Wi-Fi before anything else.

main selects it on every boot that has credentials. A connection hands over to
the normal startup app. A failure (wrong password, renamed network, new box)
says so and waits for OK, which reboots into the setup portal on the access
point, credentials kept so the form comes back filled in.
"""

import app_registry
import ticks
from apps.base_app import BaseApp
from ui import screen_ids

# The updater waits 25 s for the same connection; a working network answers in
# a few seconds, so 20 s only ever delays a boot that is going to fail anyway.
CONNECT_TIMEOUT_MS = 20000

CHECK_COLOR = 0x1565C0
FAILED_COLOR = 0xD32F2F

_CONNECTING = "connecting"
_FAILED = "failed"


class WifiCheckApp(BaseApp):
    APP_ID = "wifi_check_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = None
        self._state = _CONNECTING
        self._deadline = 0

    def on_enter(self):
        super().on_enter()
        self._state = _CONNECTING
        self._screen = self.screen_manager.get(screen_ids.SIMPLE_MESSAGE)
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._screen.configure(
            title=self.t("wifi_check.title"),
            message=self.t("wifi_check.connecting"),
            title_bg_color=CHECK_COLOR,
            show_ok_button=False,
        )
        # HardwareManager.tick() starts and drives the connection from the
        # main loop; this app only watches it, so LVGL and the watchdog keep
        # being serviced while it waits.
        self.hardware.wifi.request_connection()
        self._deadline = ticks.ticks_add(ticks.ticks_ms(), CONNECT_TIMEOUT_MS)

    def tick(self):
        if self._state == _FAILED:
            button = self.hardware.button
            if button and button.was_short_pressed():
                self._restart_on_setup_access_point()
            return None

        wifi = self.hardware.wifi
        if wifi.is_connected():
            return app_registry.STARTUP
        if wifi.has_failed() or ticks.ticks_diff(ticks.ticks_ms(), self._deadline) >= 0:
            self._show_failure()
        return None

    def _show_failure(self):
        self._state = _FAILED
        self._screen.configure(
            title=self.t("wifi_check.failed_title"),
            message=self.t("wifi_check.failed_message"),
            title_bg_color=FAILED_COLOR,
            show_ok_button=True,
        )

    def _restart_on_setup_access_point(self):
        # A reboot rather than a switch to Settings: the portal then starts on
        # the fresh heap it was sized for, with no station left retrying.
        import machine
        import nvs_store

        try:
            nvs_store.write_setup_ap_flag(True)
        except Exception as e:
            print("[wifi_check] setup_ap flag write failed:", e)
        self.hardware.wifi.abandon()
        machine.reset()
