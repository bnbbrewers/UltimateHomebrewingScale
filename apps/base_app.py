"""
Base application class with no direct LVGL dependency.
"""

from ui import screen_ids


class BaseApp:
    APP_ID = None
    LONG_PRESS_DURATION_MS = 3000

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        self.screen_manager = screen_manager
        self.hardware = hardware
        self.apis = apis
        self.i18n = i18n

        self._active = False

    def t(self, key, *args, **kwargs):
        if self.i18n:
            return self.i18n.t(key, *args, **kwargs)
        return key

    def on_enter(self):
        self._active = True
        button = self.hardware.button
        if button and hasattr(button, "long_press_duration_ms"):
            button.long_press_duration_ms = self.LONG_PRESS_DURATION_MS

    def on_exit(self):
        self._active = False

    def release_screen_refs(self):
        for attr in (
            "_screen",
            "_select_screen",
            "_weigh_screen",
            "_simple_screen",
            "_volume_screen",
            "_weight_screen",
        ):
            try:
                if hasattr(self, attr):
                    setattr(self, attr, None)
            except Exception:
                pass

    def release_runtime_state(self):
        """Release app-owned transient references before another app enters."""
        self.release_screen_refs()
        api = getattr(self, "_api", None)
        close_http = getattr(api, "close_http", None)
        if close_http:
            close_http()

    def tick(self):
        return None

    def _check_return_to_launcher(self):
        button = self.hardware.button
        if button and button.was_long_pressed():
            return True
        return False

    def _show_msg(self, title, message, bar_color=0x333333, show_ok=False):
        scr = self.screen_manager.get(screen_ids.SIMPLE_MESSAGE)
        if not scr:
            return False
        scr.configure(
            title=title,
            message=message,
            title_bg_color=bar_color,
            show_ok_button=show_ok,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        return True

    def _rotary_navigate(self, idx, count):
        r = self.hardware.rotary
        if not r:
            return idx, False
        return r.navigate_index(idx, count, wrap=False, invert=False)

    def _read_and_update_weight(self, screen):
        scale = self.hardware.scale
        if scale is None:
            if screen:
                screen.set_status("Scale not found")
            return None

        weight = scale.read_weight_filtered()
        if weight is None:
            return None

        if screen:
            screen.update_from_weight(weight)
        return weight
