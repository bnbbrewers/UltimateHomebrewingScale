"""
Speaker device abstraction for safe, centralized audio feedback.
"""


_SHARED_SPEAKER = None


class SpeakerDevice:
    def __init__(self, raw_speaker=None):
        self._raw_speaker = raw_speaker
        if self._raw_speaker is None:
            try:
                import M5
                self._raw_speaker = M5.Speaker
            except Exception:
                self._raw_speaker = None
        self._started = False

    def __bool__(self):
        return self.available()

    def available(self):
        return self._raw_speaker is not None

    def begin(self):
        if self._raw_speaker is None:
            return False
        if self._started:
            return True
        try:
            self._raw_speaker.begin()
            self._started = True
            return True
        except Exception:
            return False

    def tone(self, frequency=4000, duration_ms=50):
        if self._raw_speaker is None:
            return False
        try:
            self._raw_speaker.tone(int(frequency), int(duration_ms))
            return True
        except Exception:
            return False

    def selection_beep(self):
        return self.tone(4000, 50)

    def rotary_beep(self):
        return self.tone(4000, 50)

    def button_short_beep(self):
        return self.tone(3200, 45)

    def button_long_beep(self):
        return self.tone(1900, 140)


def get_speaker():
    global _SHARED_SPEAKER
    if _SHARED_SPEAKER is None:
        _SHARED_SPEAKER = SpeakerDevice()
    return _SHARED_SPEAKER
