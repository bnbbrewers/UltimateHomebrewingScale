"""
Hidden app: the saved Wi-Fi could not be joined.

The launcher opens it once the background connection has failed (wrong
password, renamed network, new router). It waits for OK, which reboots into
the setup portal on the access point, credentials kept so the form comes back
filled in.
"""

from apps.base_app import BaseApp
from ui import screen_ids

PROBLEM_COLOR = 0xD32F2F


class WifiProblemApp(BaseApp):
    APP_ID = "wifi_problem_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = None

    def on_enter(self):
        super().on_enter()
        self._screen = self.screen_manager.get(screen_ids.SIMPLE_MESSAGE)
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._screen.configure(
            title=self.t("wifi_problem.title"),
            message=self.t("wifi_problem.message"),
            title_bg_color=PROBLEM_COLOR,
            show_ok_button=True,
        )

    def tick(self):
        button = self.hardware.button
        if button and button.was_short_pressed():
            self._restart_on_setup_access_point()
        return None

    def _restart_on_setup_access_point(self):
        # A reboot rather than a switch to Settings: the portal then starts on
        # the fresh heap it was sized for, with no station left retrying.
        import machine
        import nvs_store

        try:
            nvs_store.write_setup_ap_flag(True)
        except Exception as e:
            print("[wifi_problem] setup_ap flag write failed:", e)
        self.hardware.wifi.abandon()
        machine.reset()
