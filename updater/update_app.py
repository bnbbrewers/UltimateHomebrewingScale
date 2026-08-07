# -*- coding: utf-8 -*-
"""
Hidden updater app.

This app is intentionally not present in the launcher. It can be selected as an
initial app by firmware/startup code when an update has been requested.
"""

from apps.base_app import BaseApp
from ui import screen_ids

try:
    import config as _config

    _DEBUG = bool(getattr(_config, "DEBUG", False))
except Exception:
    _DEBUG = False

try:
    from memory_debug import snapshot as _debug_snapshot
except Exception:
    _debug_snapshot = None


UPDATE_COLOR = 0x1565C0


def _mem_snapshot(tag):
    if _DEBUG and _debug_snapshot:
        try:
            _debug_snapshot(tag, enabled=True, collect=False)
        except Exception:
            pass


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
        self._screen = self.screen_manager.get(screen_ids.SIMPLE_MESSAGE)
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._screen.configure(
            title=self._text("updater.title", "Updater"),
            message=self._text("updater.ready", "Preparation..."),
            title_bg_color=UPDATE_COLOR,
            show_ok_button=False,
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
            self._screen.set_message(self._text("updater.wifi_connecting", "Connecting Wi-Fi"))
            self._flush_lvgl()
            wifi = self.hardware.wifi
            if wifi is not None and hasattr(wifi, "ensure_connected"):
                if not wifi.ensure_connected(timeout_s=25):
                    raise RuntimeError("WiFi connect timeout")

            _mem_snapshot("updater_app.before_import_runner")
            from updater.workflow import update
            _mem_snapshot("updater_app.after_import_runner")

            result = update(
                channel=self._update_channel(),
                progress_callback=self._on_progress,
                wifi_device=self.hardware.wifi,
                ensure_wifi=False,
                i18n=self.i18n,
            )
            # Keep the request set when the update fails so a later reboot can
            # retry. This legacy UI path mirrors updater.boot behaviour.
            if not (isinstance(result, dict) and result.get("more_updates")):
                self._clear_update_request()
            self._waiting_restart = True
            self._screen.configure(
                title=self._text("updater.title", "Updater"),
                message=self._text("updater.done_restart", "updater.done_restart"),
                title_bg_color=UPDATE_COLOR,
                show_ok_button=True,
            )
            self._flush_lvgl()
        except Exception as e:
            self._failed = True
            self._screen.configure(
                title=self._text("updater.error", "Erreur"),
                message=str(e),
                title_bg_color=0xD32F2F,
                show_ok_button=True,
            )
            self._flush_lvgl()
            try:
                import sys

                sys.print_exception(e)
            except Exception:
                try:
                    print("[updater] error:", e)
                except Exception:
                    pass

    def _on_progress(self, event):
        message = event.get("message", "")
        detail = event.get("detail", "")
        current = event.get("current", 0)
        total = event.get("total", 0)
        if current and total:
            message = "{} {}/{}".format(message, current, total)
        if event.get("stage") == "release":
            message = self._text("updater.searching_version", "Searching for a new version...")
        if detail:
            message = "{}\n{}".format(message, detail)
        self._screen.set_message(message)
        self._flush_lvgl()

    def _update_channel(self):
        try:
            import config

            value = getattr(config, "UPDATE_CHANNEL", "stable")
        except Exception:
            value = "stable"
        value = str(value or "stable").strip().lower()
        if value != "prerelease":
            return "stable"
        return "prerelease"

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
