"""
Button device abstraction for consistent short/long press handling.
"""

import time
from devices.speaker import get_speaker

try:
    import config
    _BUTTON_SHORT_BEEP_ENABLED = getattr(config, "BUTTON_SHORT_BEEP_ENABLED", True)
    _BUTTON_LONG_BEEP_ENABLED = getattr(config, "BUTTON_LONG_BEEP_ENABLED", True)
except Exception:
    _BUTTON_SHORT_BEEP_ENABLED = True
    _BUTTON_LONG_BEEP_ENABLED = True


class ButtonDevice:
    def __init__(self, raw_button, button_id="A", long_press_duration_ms=3000):
        self._raw_button = raw_button
        self.button_id = button_id
        self.long_press_duration_ms = long_press_duration_ms

        self._is_pressed = False
        self._press_start_ms = 0
        self._long_fired = False
        self._short_event = False
        self._long_event = False

    def tick(self):
        self._update_state()

    def _update_state(self):
        if self._raw_button is None:
            return

        now = time.ticks_ms()
        pressed = self._raw_button.isPressed()

        if pressed:
            if not self._is_pressed:
                self._is_pressed = True
                self._press_start_ms = now
                self._long_fired = False
            elif not self._long_fired:
                elapsed = time.ticks_diff(now, self._press_start_ms)
                if elapsed >= self.long_press_duration_ms:
                    self._long_fired = True
                    self._long_event = True
                    if _BUTTON_LONG_BEEP_ENABLED:
                        speaker = get_speaker()
                        if speaker:
                            speaker.button_long_beep()
        else:
            if self._is_pressed and not self._long_fired:
                self._short_event = True
                if _BUTTON_SHORT_BEEP_ENABLED:
                    speaker = get_speaker()
                    if speaker:
                        speaker.button_short_beep()
            self._is_pressed = False
            self._long_fired = False

    def is_pressed(self):
        self._update_state()
        return self._is_pressed

    def was_short_pressed(self):
        self._update_state()
        if self._short_event:
            self._short_event = False
            return True
        return False

    def was_long_pressed(self):
        self._update_state()
        if self._long_event:
            self._long_event = False
            return True
        return False

    # Compatibility helpers (same style as M5 BtnA API)
    def isPressed(self):
        return self.is_pressed()

    def wasPressed(self):
        return self.was_short_pressed()
