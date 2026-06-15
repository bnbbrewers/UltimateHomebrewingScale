# -*- coding: utf-8 -*-
"""
Hidden updater app.

This app is intentionally not present in the launcher. It can be selected as an
initial app by firmware/startup code when an update has been requested.
"""

from .base_app import BaseApp
from ui import screen_ids


UPDATE_COLOR = 0x1565C0


class UpdaterApp(BaseApp):
    APP_ID = "updater_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._screen = None
        self._waiting_restart = False
        self._failed = False

    def on_enter(self):
        super().on_enter()
        self._waiting_restart = False
        self._failed = False
        self._screen = self.screen_manager.get(screen_ids.UPDATER)
        self.screen_manager.show(screen_ids.UPDATER)
        self._screen.configure(
            title=self._text("updater.title", "Updater"),
            title_bg_color=UPDATE_COLOR,
        )
        self._flush_lvgl()
        self._run_update()

    def tick(self):
        button = self.hardware.button
        if self._waiting_restart and button and button.was_short_pressed():
            self._soft_reset()
            return None
        if self._failed and button and button.was_short_pressed():
            return "launcher"
        return None

    def _run_update(self):
        try:
            from core import updater

            updater.update(
                branch=self._update_branch(),
                progress_callback=self._on_progress,
                wifi_device=self.hardware.wifi,
                i18n=self.i18n,
            )
            self._waiting_restart = True
            self._screen.show_done(self._text("updater.done_restart", "updater.done_restart"))
            self._flush_lvgl()
        except Exception as e:
            self._failed = True
            self._screen.show_error(str(e))
            self._flush_lvgl()
            try:
                import sys

                sys.print_exception(e)
            except Exception:
                try:
                    print("[updater] error:", e)
                except Exception:
                    pass
        finally:
            self._clear_update_request()

    def _on_progress(self, event):
        message = event.get("message", "")
        detail = event.get("detail", "")
        current = event.get("current", 0)
        total = event.get("total", 0)
        if current and total:
            message = "{} {}/{}".format(message, current, total)
        self._screen.set_status(message, detail)
        self._screen.set_progress(event.get("percent", 0))
        self._flush_lvgl()

    def _update_branch(self):
        try:
            import config

            return getattr(config, "UPDATE_BRANCH", "main")
        except Exception:
            return "main"

    def _text(self, key, fallback):
        if self.i18n:
            return self.i18n.t(key)
        return fallback

    def _clear_update_request(self):
        try:
            from storage import config_registry

            config_registry.set_update_requested(False)
        except Exception as e:
            try:
                print("[updater] clear update flag error:", e)
            except Exception:
                pass

    def _soft_reset(self):
        try:
            import machine

            machine.reset()
        except Exception:
            try:
                import M5

                M5.Power.reset()
            except Exception:
                pass
