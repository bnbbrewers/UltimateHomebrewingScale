"""Optional idle standby.

The device enters ESP32 deep sleep after STANDBY_TIMEOUT_MIN minutes without
operator activity, and wakes when the screen is touched. The feature stays
completely disabled unless the setting is present and valid.

Waking is a full reboot: the main button cannot wake this board, GPIO42 is not
an RTC GPIO on the ESP32-S3, so the wake source is the touch interrupt.

This module must stay dependency-light: no UI, no application managers, no
network clients, and no retained references to any of them.
"""

_MIN_TIMEOUT_MIN = 1
_MAX_TIMEOUT_MIN = 240
_DEFAULT_WEIGHT_TOLERANCE_G = 5
_WEIGHT_SAMPLE_MS = 1000
_TOUCH_INT_PIN = 14
_DEFAULT_RELAY_IO = (1, 2)
_INHIBITING_APPS = ("updater_app", "scale_calibration_wizard_app")


class StandbyManager:
    def __init__(self, timeout_ms, weight_tolerance_g=_DEFAULT_WEIGHT_TOLERANCE_G,
                 relay_pin=_DEFAULT_RELAY_IO[1], machine_module=None,
                 esp32_module=None, time_module=None, display=None, logger=None):
        self.timeout_ms = timeout_ms
        self.enabled = timeout_ms is not None
        self.weight_tolerance_g = weight_tolerance_g
        self.relay_pin = relay_pin
        self._machine = machine_module
        self._esp32 = esp32_module
        self._time = time_module
        self._display = display
        self._logger = logger or print
        self._idle_since_ms = None
        self._last_rotary = None
        self._last_weight = None
        self._last_weight_sample_ms = None

    def note_activity(self):
        if not self.enabled or self._time is None:
            return
        self._idle_since_ms = self._time.ticks_ms()

    def _sample_activity(self, hardware, now_ms):
        active = False

        button = getattr(hardware, "button", None)
        if button is not None:
            try:
                if button.is_pressed():
                    active = True
            except Exception:
                pass

        rotary = getattr(hardware, "rotary", None)
        if rotary is not None:
            try:
                value = rotary.get_rotary_value()
            except Exception:
                value = None
            if value is not None:
                if self._last_rotary is None:
                    self._last_rotary = value
                elif value != self._last_rotary:
                    self._last_rotary = value
                    active = True

        scale = getattr(hardware, "scale", None)
        if scale is not None and self._weight_sample_due(now_ms):
            self._last_weight_sample_ms = now_ms
            try:
                weight = scale.read_weight_filtered()
            except Exception:
                weight = None
            if weight is not None:
                previous = self._last_weight
                self._last_weight = weight
                if previous is not None and abs(weight - previous) > self.weight_tolerance_g:
                    active = True

        return active

    def _weight_sample_due(self, now_ms):
        if self._last_weight_sample_ms is None:
            return True
        if self._time is None:
            return False
        return self._time.ticks_diff(now_ms, self._last_weight_sample_ms) >= _WEIGHT_SAMPLE_MS

    def tick(self, hardware, app_manager=None):
        if not self.enabled:
            return False
        try:
            now_ms = self._time.ticks_ms()
            if self._idle_since_ms is None:
                self._idle_since_ms = now_ms
            if self._sample_activity(hardware, now_ms):
                self._idle_since_ms = now_ms
                return False
            if self._time.ticks_diff(now_ms, self._idle_since_ms) < self.timeout_ms:
                return False
            return self.sleep_now()
        except Exception as error:
            self._logger("Standby tick failed: %s" % error)
            return False

    def sleep_now(self):
        """Replaced in Task 4. Sleeping is not implemented yet."""
        return True


def _configured_timeout_ms(config_module, logger):
    try:
        minutes = getattr(config_module, "STANDBY_TIMEOUT_MIN")
    except AttributeError:
        return None

    if isinstance(minutes, bool) or not isinstance(minutes, int):
        logger("STANDBY_TIMEOUT_MIN ignored: expected an integer")
        return None
    if minutes == 0:
        return None
    if minutes < _MIN_TIMEOUT_MIN or minutes > _MAX_TIMEOUT_MIN:
        logger("STANDBY_TIMEOUT_MIN ignored: expected 0 or %d-%d minutes"
               % (_MIN_TIMEOUT_MIN, _MAX_TIMEOUT_MIN))
        return None
    return minutes * 60 * 1000


def _configured_weight_tolerance(config_module):
    value = getattr(config_module, "HOP_WEIGHT_TOLERANCE", None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _DEFAULT_WEIGHT_TOLERANCE_G
    if value <= 0:
        return _DEFAULT_WEIGHT_TOLERANCE_G
    return value


def _configured_relay_pin(config_module):
    relay_io = getattr(config_module, "KEG_RELAY_IO", _DEFAULT_RELAY_IO)
    try:
        return int(relay_io[1])
    except Exception:
        return _DEFAULT_RELAY_IO[1]


def configure(config_module, machine_module=None, esp32_module=None,
              time_module=None, display=None, logger=None):
    """Configure the optional idle standby. Returns an inert manager when off."""
    log = logger or print
    timeout_ms = _configured_timeout_ms(config_module, log)
    if timeout_ms is None:
        return StandbyManager(None, logger=log)

    if machine_module is None:
        try:
            import machine as machine_module
        except Exception as error:
            log("Standby unavailable: %s" % error)
            return StandbyManager(None, logger=log)
    if esp32_module is None:
        try:
            import esp32 as esp32_module
        except Exception as error:
            log("Standby unavailable: %s" % error)
            return StandbyManager(None, logger=log)
    if time_module is None:
        try:
            import time as time_module
        except Exception as error:
            log("Standby unavailable: %s" % error)
            return StandbyManager(None, logger=log)
    if display is None:
        try:
            import M5
            display = M5.Display
        except Exception:
            display = None

    manager = StandbyManager(
        timeout_ms,
        weight_tolerance_g=_configured_weight_tolerance(config_module),
        relay_pin=_configured_relay_pin(config_module),
        machine_module=machine_module,
        esp32_module=esp32_module,
        time_module=time_module,
        display=display,
        logger=log,
    )
    manager.note_activity()
    return manager
