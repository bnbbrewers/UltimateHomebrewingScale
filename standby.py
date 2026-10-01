"""Optional idle standby.

After STANDBY_TIMEOUT_MIN minutes without operator activity the device powers
itself off, and pressing the knob brings it back with a full boot. The feature
stays completely disabled unless the setting is present and valid.

Power off means releasing the supply latch. On the battery connector that cuts
the power for good, and the knob, wired to the power-on circuit, closes it
again. On USB or the 5 V connector the latch changes nothing: the board stays
up with a black screen until the knob is pressed, then restarts. Both supplies
therefore look the same to the operator. Deep sleep is not used: the knob,
GPIO42, is not an RTC GPIO on the ESP32-S3 and could not wake it.

This module must stay dependency-light: no UI, no application managers, no
network clients, and no retained references to any of them.
"""

_MIN_TIMEOUT_MIN = 1
_MAX_TIMEOUT_MIN = 240
_DEFAULT_WEIGHT_TOLERANCE_G = 5
_WEIGHT_SAMPLE_MS = 1000
# The knob pulls this pad low while pressed.
_KNOB_PIN = 42
_KNOB_POLL_MS = 20
# On the battery connector the supply latch stays closed only while this pad
# is driven high; M5Unified raises it at boot.
_POWER_HOLD_PIN = 46
_DEFAULT_RELAY_IO = (1, 2)


class StandbyManager:
    def __init__(self, timeout_ms, weight_tolerance_g=_DEFAULT_WEIGHT_TOLERANCE_G,
                 relay_pin=_DEFAULT_RELAY_IO[1], machine_module=None,
                 time_module=None, display=None, watchdog_feed=None, logger=None):
        self.timeout_ms = timeout_ms
        self.enabled = timeout_ms is not None
        self.weight_tolerance_g = weight_tolerance_g
        self.relay_pin = relay_pin
        self._machine = machine_module
        self._time = time_module
        self._display = display
        self._watchdog_feed = watchdog_feed
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
                # The active app clears the raw value before this sample, so
                # a turn is only visible through the device's own marker.
                marker = getattr(rotary, "activity_marker", None)
                value = marker() if marker else rotary.get_rotary_value()
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

    def _inhibited(self, app_manager):
        """Ask the app manager whether sleeping now would interrupt something.

        Activity sampling alone is not enough: a keg filling slowly changes
        weight by less than the tolerance between two samples, so the idle
        countdown would run out mid-fill and reboot the device.

        The manager answers for both reasons an app can refuse to sleep: it is
        inherently uninterruptible, or it is in the middle of an operation.
        The older active_app_id() path is kept as a fallback so this module
        still works with a manager that only exposes that.
        """
        if app_manager is None:
            return False
        asks = getattr(app_manager, "standby_inhibited", None)
        if asks is not None:
            try:
                return bool(asks())
            except Exception:
                return False
        getter = getattr(app_manager, "active_app_id", None)
        if getter is None:
            return False
        try:
            import app_registry

            return app_registry.inhibits_standby(getter())
        except Exception:
            return False

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
            if self._inhibited(app_manager):
                self._idle_since_ms = now_ms
                return False
            if self._time.ticks_diff(now_ms, self._idle_since_ms) < self.timeout_ms:
                return False
            return self.sleep_now()
        except Exception as error:
            self._logger("Standby tick failed: %s" % error)
            return False

    def _abort_sleep(self, reason, restore_brightness):
        self._logger("Standby did not sleep: %s" % reason)
        if restore_brightness is not None and self._display is not None:
            try:
                self._display.setBrightness(restore_brightness)
            except Exception:
                pass
        self.note_activity()
        return False

    def _wait_for_knob_press(self, knob):
        """Block until the knob goes from released to pressed.

        A knob already held when standby starts must be released first, so a
        stuck reading cannot turn standby into a restart loop. The runtime
        watchdog, when armed, would otherwise reset the board mid-wait.
        """
        released = False
        while True:
            if self._watchdog_feed is not None:
                try:
                    self._watchdog_feed()
                except Exception:
                    pass
            pressed = knob.value() == 0
            if released and pressed:
                return
            if not pressed:
                released = True
            self._time.sleep_ms(_KNOB_POLL_MS)

    def sleep_now(self):
        """Pin the relay line, black out the screen and release the power
        latch; when the board is still powered, restart on a knob press."""
        if self._machine is None or self._time is None:
            return self._abort_sleep("platform modules unavailable", None)

        Pin = self._machine.Pin
        try:
            Pin(self.relay_pin, Pin.OUT, value=0)
        except Exception as error:
            return self._abort_sleep("relay line could not be pinned: %s" % error, None)
        try:
            knob = Pin(_KNOB_PIN, Pin.IN, Pin.PULL_UP)
        except Exception as error:
            # Without the knob nothing could bring a USB-powered board back.
            return self._abort_sleep("knob could not be read: %s" % error, None)

        if self._display is not None:
            try:
                self._display.setBrightness(0)
            except Exception as error:
                self._logger("Standby could not dim the display: %s" % error)

        try:
            Pin(_POWER_HOLD_PIN, Pin.OUT, value=0)
        except Exception as error:
            self._logger("Standby could not release the power latch: %s" % error)

        # Still running: the supply is external, so wait in the dark.
        self._wait_for_knob_press(knob)
        self._machine.reset()
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


def configure(config_module, machine_module=None, time_module=None,
              display=None, watchdog_feed=None, logger=None):
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
    if watchdog_feed is None:
        try:
            import runtime_watchdog
            watchdog_feed = runtime_watchdog.feed
        except Exception:
            watchdog_feed = None

    manager = StandbyManager(
        timeout_ms,
        weight_tolerance_g=_configured_weight_tolerance(config_module),
        relay_pin=_configured_relay_pin(config_module),
        machine_module=machine_module,
        time_module=time_module,
        display=display,
        watchdog_feed=watchdog_feed,
        logger=log,
    )
    manager.note_activity()
    return manager
