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

    def _release_hold(self):
        try:
            self._esp32.gpio_deep_sleep_hold(False)
        except Exception:
            pass
        try:
            self._machine.Pin(self.relay_pin, self._machine.Pin.OUT,
                              value=0, hold=False)
        except Exception:
            pass

    def _abort_sleep(self, reason, restore_brightness):
        self._logger("Standby did not sleep: %s" % reason)
        self._release_hold()
        if restore_brightness is not None and self._display is not None:
            try:
                self._display.setBrightness(restore_brightness)
            except Exception:
                pass
        self.note_activity()
        return False

    def sleep_now(self):
        """Pin the relay line, arm the touch wake, and enter deep sleep."""
        if self._machine is None or self._esp32 is None:
            return self._abort_sleep("platform modules unavailable", None)

        try:
            self._machine.Pin(self.relay_pin, self._machine.Pin.OUT,
                              value=0, hold=True)
            self._esp32.gpio_deep_sleep_hold(True)
        except Exception as error:
            return self._abort_sleep("relay line could not be pinned: %s" % error, None)

        previous_brightness = None
        if self._display is not None:
            try:
                previous_brightness = self._display.getBrightness()
            except Exception:
                previous_brightness = None
            try:
                self._display.setBrightness(0)
            except Exception as error:
                self._logger("Standby could not dim the display: %s" % error)

        try:
            self._esp32.wake_on_ext0(
                pin=self._machine.Pin(_TOUCH_INT_PIN, self._machine.Pin.IN),
                level=self._esp32.WAKEUP_ALL_LOW,
            )
        except Exception as error:
            # Sleeping with no wake source would need a physical power cycle.
            return self._abort_sleep("wake source could not be armed: %s" % error,
                                     previous_brightness)

        self._machine.deepsleep()
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
