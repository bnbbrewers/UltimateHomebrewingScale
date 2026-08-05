"""
Settings app: QR-only entrypoint for smartphone setup portal.
"""

import os

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
        self._portal_status_shown = False
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

    @staticmethod
    def _file_exists(path):
        try:
            return os.path.exists(path)
        except AttributeError:
            try:
                os.stat(path)
                return True
            except OSError:
                return False

    @staticmethod
    def _copy_file(src, dst):
        with open(src, "rb") as source:
            with open(dst, "wb") as target:
                while True:
                    chunk = source.read(1024)
                    if not chunk:
                        break
                    target.write(chunk)

    @classmethod
    def _ensure_config_file(cls, config_path="config.py", example_path="config.py.example"):
        if cls._file_exists(config_path):
            return False
        if not cls._file_exists(example_path):
            return False
        cls._copy_file(example_path, config_path)
        try:
            print("[settings] config.py created from config.py.example")
        except Exception:
            pass
        return True

    def on_enter(self):
        super().on_enter()
        self._tick_error_logged = False
        self._portal_status_shown = False
        self._ensure_config_file()
        try:
            import gc

            gc.collect()
            gc.collect()
            if self._portal is None:
                if self._debug:
                    try:
                        print("[MEM] settings.pre_import free={}".format(gc.mem_free()))
                    except Exception:
                        pass
                from webportal.setup_portal_service import SetupPortalService
                debug_portal = False
                try:
                    import config

                    debug_portal = bool(getattr(config, "DEBUG", False))
                except Exception:
                    pass

                self._portal = SetupPortalService(
                    wifi_device=self.hardware.wifi,
                    debug=debug_portal,
                    i18n=self.i18n,
                    before_client=self._release_screen_for_portal_client,
                )
                gc.collect()
                if self._debug:
                    try:
                        print("[MEM] settings.post_import free={}".format(gc.mem_free()))
                    except Exception:
                        pass

            info = self._portal.start_or_resume()
            if self._debug:
                try:
                    print("[settings] portal mode={} url={}".format(info.get("mode", "?"), info.get("url", "")))
                except Exception:
                    pass
            if self._screen is None:
                self._screen = self.screen_manager.get(screen_ids.SETTINGS)
            mode = info.get("mode", "sta")
            if mode == "ap":
                status = self.t("settings.portal_connect_ap")
            else:
                status = self.t("settings.portal_connect_sta")
            self.screen_manager.show(screen_ids.SETTINGS)
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
                    self.screen_manager.show(screen_ids.SETTINGS)
            except Exception:
                pass

    def on_exit(self):
        super().on_exit()
        portal = self._portal
        self._portal = None
        if portal:
            try:
                portal.stop()
            except Exception as e:
                self._print_exception("[settings] portal stop error:", e)
        self._screen = None
        try:
            import gc

            gc.collect()
        except Exception:
            pass

    def _release_screen_for_portal_client(self):
        self._portal_status_shown = True
        if self._debug:
            try:
                print("[settings] portal client cleanup begin")
            except Exception:
                pass
        self._screen = None
        cleanup = getattr(self.screen_manager, "memory_cleanup", None)
        if cleanup:
            try:
                cleanup(
                    loading_message=self.t("settings.portal_in_progress"),
                    loading_color=0x7E57C2,
                )
                if self._debug:
                    try:
                        print("[settings] portal client cleanup done via memory_cleanup")
                    except Exception:
                        pass
                return
            except Exception:
                pass
        try:
            self.screen_manager.release(screen_ids.SETTINGS)
            if self._debug:
                try:
                    print("[settings] portal client cleanup done via release")
                except Exception:
                    pass
        except Exception:
            pass

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"
        try:
            if self._portal:
                self._portal.tick()
                consume_events = getattr(self._portal, "consume_events", None)
                if consume_events:
                    for event in consume_events():
                        if event == "INITIAL_PAGE_SERVED" and not self._portal_status_shown:
                            self._portal_status_shown = True
                            self._release_screen_for_portal_client()
        except Exception as e:
            if not self._tick_error_logged:
                self._tick_error_logged = True
                self._print_exception("[settings] portal tick error:", e)
        return None
