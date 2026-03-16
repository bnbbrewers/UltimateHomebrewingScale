"""
Base application class with no direct LVGL dependency.
"""

import time


class BaseApp:
    APP_ID = None
    LONG_PRESS_DURATION_MS = 3000

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        self.screen_manager = screen_manager
        self.hardware = hardware
        self.apis = apis
        self.i18n = i18n

        self._active = False
        self._btn_is_pressed = False
        self._btn_press_start = 0

    def t(self, key, *args, **kwargs):
        if self.i18n:
            return self.i18n.t(key, *args, **kwargs)
        return key

    def on_enter(self):
        self._active = True
        self._btn_is_pressed = False

    def on_exit(self):
        self._active = False
        self._btn_is_pressed = False

    def tick(self):
        return None

    def _check_return_to_launcher(self):
        button = self.hardware.button
        if button.isPressed():
            if not self._btn_is_pressed:
                self._btn_is_pressed = True
                self._btn_press_start = time.ticks_ms()
            else:
                elapsed = time.ticks_diff(time.ticks_ms(), self._btn_press_start)
                if elapsed >= self.LONG_PRESS_DURATION_MS:
                    return True
        else:
            self._btn_is_pressed = False
        return False
