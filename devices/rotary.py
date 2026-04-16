"""
Rotary encoder device abstraction.
Centralizes rotary reads and index navigation helpers.
"""

from devices.speaker import get_speaker

try:
    import config
    _ROTARY_BEEP_ENABLED = getattr(config, "ROTARY_BEEP_ENABLED", True)
except Exception:
    _ROTARY_BEEP_ENABLED = True


class RotaryDevice:
    def __init__(self, raw_rotary=None):
        self._raw_rotary = raw_rotary
        if self._raw_rotary is None:
            try:
                from hardware import Rotary
                self._raw_rotary = Rotary()
            except Exception:
                self._raw_rotary = None

    def __bool__(self):
        return self.available()

    def available(self):
        return self._raw_rotary is not None

    def reset(self):
        if self._raw_rotary is not None:
            self._raw_rotary.reset_rotary_value()

    def consume_delta(self):
        if self._raw_rotary is None:
            return 0
        delta = self._raw_rotary.get_rotary_value()
        if delta:
            self._raw_rotary.reset_rotary_value()
            if _ROTARY_BEEP_ENABLED:
                speaker = get_speaker()
                if speaker:
                    speaker.rotary_beep()
        return delta

    def navigate_index(self, idx, count, wrap=False, invert=False):
        if count <= 0:
            return idx, False
        delta = self.consume_delta()
        if not delta:
            return idx, False
        step = 1 if delta > 0 else -1
        if invert:
            step = -step
        idx += step
        if wrap:
            if idx < 0:
                idx = count - 1
            elif idx >= count:
                idx = 0
        else:
            if idx < 0:
                idx = 0
            elif idx >= count:
                idx = count - 1
        return idx, True

    # Compatibility helpers (same names as the low-level rotary API)
    def get_rotary_value(self):
        if self._raw_rotary is None:
            return 0
        return self._raw_rotary.get_rotary_value()

    def reset_rotary_value(self):
        self.reset()
