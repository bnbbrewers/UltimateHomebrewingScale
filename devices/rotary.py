"""
Rotary encoder device abstraction.
Centralizes rotary reads, index navigation and the back gesture.
"""

from ticks import ticks_diff, ticks_ms

# Sign of a left (counter-clockwise) turn in the raw count. Checked on the
# M5Dial by turning the dial left, not taken from the launcher comment.
LEFT_DIRECTION = -1
# An eighth of a turn, in raw counts. Measured on the M5Dial: the driver
# decodes full steps, one count per click, and two clicks make the gesture.
BACK_GESTURE_COUNTS = 2
# Left counts further apart than this are not one gesture: knocks spread over
# time must never add up to a step back.
BACK_GESTURE_IDLE_MS = 800


class RotaryDevice:
    def __init__(self, raw_rotary=None, clock=ticks_ms):
        self._raw_rotary = raw_rotary
        if self._raw_rotary is None:
            try:
                from hardware import Rotary
                self._raw_rotary = Rotary()
            except Exception:
                self._raw_rotary = None
        self._clock = clock
        self._back_counts = 0
        self._back_last_ms = 0
        self._moved = 0

    def __bool__(self):
        return self.available()

    def available(self):
        return self._raw_rotary is not None

    def reset(self):
        self._back_counts = 0
        if self._raw_rotary is not None:
            self._moved += abs(self._raw_rotary.get_rotary_value())
            self._raw_rotary.reset_rotary_value()

    def _read(self):
        if self._raw_rotary is None:
            return 0
        delta = self._raw_rotary.get_rotary_value()
        if delta:
            self._raw_rotary.reset_rotary_value()
            self._moved += abs(delta)
        return delta

    def consume_delta(self):
        # Whoever reads the dial to navigate owns the turn: it must not leave
        # half a gesture behind for the next screen.
        self._back_counts = 0
        return self._read()

    def consume_back_gesture(self):
        """True once the dial has turned an eighth of a turn to the left.

        Consumes the pending count. Only left rotation accumulates: a turn to
        the right, or a pause of BACK_GESTURE_IDLE_MS, starts over.
        """
        left = self._read() * LEFT_DIRECTION
        now = self._clock()
        if self._back_counts and ticks_diff(now, self._back_last_ms) >= BACK_GESTURE_IDLE_MS:
            self._back_counts = 0
        if left <= 0:
            if left < 0:
                self._back_counts = 0
            return False
        self._back_counts += left
        self._back_last_ms = now
        if self._back_counts < BACK_GESTURE_COUNTS:
            return False
        self._back_counts = 0
        return True

    def activity_marker(self):
        """A value that changes whenever the dial moves.

        Standby compares it between two samples. The raw value alone is not
        enough: the active app reads and clears it before standby samples it.
        """
        pending = 0
        if self._raw_rotary is not None:
            pending = abs(self._raw_rotary.get_rotary_value())
        return self._moved + pending

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
