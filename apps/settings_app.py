"""
Settings app: QR-only entrypoint for smartphone setup portal.
"""

from .base_app import BaseApp
from ui import screen_ids


class SettingsApp(BaseApp):
    APP_ID = "settings_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = None
        self._portal = None
        self._debug = False
        self._tick_error_logged = False
        try:
            import config

            self._debug = bool(getattr(config, "DEBUG", False))
        except Exception:
            self._debug = False

    @staticmethod
    def _print_exception(prefix, exc):
        try:
            print(prefix, exc)
        except Exception:
            pass
        try:
            import sys

            sys.print_exception(exc)
        except Exception:
            pass

    def on_enter(self):
        super().on_enter()
        self._tick_error_logged = False
        try:
            import gc

            gc.collect()
            gc.collect()
            if self._screen is None:
                self._screen = self.screen_manager.get(screen_ids.SETUP_QR)
            if self._portal is None:
                if self._debug:
                    try:
                        import gc

                        gc.collect()
                        print("[MEM] settings.pre_import free={}".format(gc.mem_free()))
                    except Exception:
                        pass
                from webportal.setup_portal import SetupPortalService
                debug_portal = False
                try:
                    import config

                    debug_portal = bool(getattr(config, "DEBUG", False))
                except Exception:
                    pass

                self._portal = SetupPortalService(wifi_device=self.hardware.wifi, debug=debug_portal, i18n=self.i18n)
                if self._debug:
                    try:
                        import gc

                        gc.collect()
                        print("[MEM] settings.post_import free={}".format(gc.mem_free()))
                    except Exception:
                        pass

            info = self._portal.start_or_resume()
            if self._debug:
                try:
                    print("[settings] portal mode={} url={}".format(info.get("mode", "?"), info.get("url", "")))
                except Exception:
                    pass
            mode = info.get("mode", "sta")
            if mode == "ap":
                status = self.t("settings.portal_connect_ap")
            else:
                status = self.t("settings.portal_connect_sta")
            self.screen_manager.show(screen_ids.SETUP_QR)
            self._flush_lvgl()
            self._screen.configure(
                title=self.t("settings.title"),
                status=status,
                url=info.get("url", "http://192.168.4.1/"),
                mode=mode,
                ap_ssid=info.get("ap_ssid", ""),
                ap_password=info.get("ap_password", ""),
            )
        except Exception as e:
            self._print_exception("[settings] portal init error:", e)
            # Requested UX: no error message on screen, console only.
            try:
                if self._screen is not None:
                    self.screen_manager.show(screen_ids.SETUP_QR)
            except Exception:
                pass


    def on_exit(self):
        super().on_exit()
        try:
            if self._portal:
                self._portal.stop()
        except Exception as e:
            self._print_exception("[settings] portal stop error:", e)
        self._portal = None

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"
        try:
            if self._portal:
                self._portal.tick()
        except Exception as e:
            if not self._tick_error_logged:
                self._tick_error_logged = True
                self._print_exception("[settings] portal tick error:", e)
        return None
