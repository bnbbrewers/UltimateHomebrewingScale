"""Optional runtime watchdog support.

The watchdog stays completely disabled unless WATCHDOG_TIMEOUT_MS is present
and valid in the private configuration module.
"""

import nvs_store

_MIN_TIMEOUT_MS = 5000
_RESET_LIMIT = 3
_HEALTHY_RUNTIME_MS = 300000
_WATCHDOG_HTTP_TIMEOUT_S = 10
# Namespace and key come from nvs_store so every reader of this slot agrees on
# it. The counter itself is read locally on purpose: an undecodable blob must
# read back as zero here, never as a byte value that could lock the
# application out, so nvs_store.get_int() is deliberately not used.
_NVS_NAMESPACE = nvs_store.APP_NAMESPACE
_NVS_COUNT_KEY = nvs_store.WATCHDOG_COUNT_KEY

_active = None


class RuntimeWatchdog:
    def __init__(self, timeout_ms, machine_module=None, nvs=None,
                 time_module=None, logger=None):
        self.timeout_ms = timeout_ms
        self.enabled = timeout_ms is not None
        self.locked = False
        self.reset_count = 0
        self._machine = machine_module
        self._nvs = nvs
        self._time = time_module
        self._logger = logger or print
        self._wdt = None
        self._armed_at_ms = None
        self._healthy_checked = False

    @property
    def running(self):
        return self._wdt is not None

    def _read_reset_count(self):
        if self._nvs is None:
            return 0
        if hasattr(self._nvs, "get_i32"):
            try:
                return max(0, int(self._nvs.get_i32(_NVS_COUNT_KEY)))
            except Exception:
                pass
        if hasattr(self._nvs, "get_blob"):
            try:
                buffer = bytearray(8)
                size = self._nvs.get_blob(_NVS_COUNT_KEY, buffer)
                if isinstance(size, int) and size > 0:
                    raw = bytes(buffer[:size])
                else:
                    raw = bytes(buffer).split(b"\x00", 1)[0]
                if raw:
                    try:
                        return max(0, int(raw.decode("utf-8")))
                    except Exception:
                        return 0
            except Exception:
                pass
        return 0

    def _write_reset_count(self, value):
        if self._nvs is None:
            return False
        try:
            if hasattr(self._nvs, "set_i32"):
                self._nvs.set_i32(_NVS_COUNT_KEY, int(value))
            elif hasattr(self._nvs, "set_blob"):
                self._nvs.set_blob(_NVS_COUNT_KEY, str(int(value)))
            else:
                raise OSError("NVS integer write API unavailable")
            self._nvs.commit()
            return True
        except Exception as error:
            self._logger("Watchdog reset counter unavailable: %s" % error)
            return False

    def process_boot(self):
        if not self.enabled or self._machine is None:
            return

        stored_count = self._read_reset_count()
        if stored_count >= _RESET_LIMIT:
            self.reset_count = stored_count
            self.locked = True
            return

        try:
            watchdog_reset = (
                self._machine.reset_cause() == self._machine.WDT_RESET
            )
        except Exception as error:
            self._logger("Unable to read reset cause: %s" % error)
            return

        if watchdog_reset:
            next_count = min(stored_count + 1, _RESET_LIMIT)
            if self._write_reset_count(next_count):
                self.reset_count = next_count
                self.locked = next_count >= _RESET_LIMIT
            return

        if stored_count:
            if self._write_reset_count(0):
                self.reset_count = 0
                return
        self.reset_count = stored_count

    def start(self, allow_start=True):
        if (not allow_start or not self.enabled or self.locked or
                self._machine is None):
            return False
        if self.running:
            return True
        try:
            self._wdt = self._machine.WDT(timeout=self.timeout_ms)
        except Exception as error:
            self._logger("Unable to start runtime watchdog: %s" % error)
            self._wdt = None
            return False

        if self._time is None:
            try:
                import time as time_module
                self._time = time_module
            except Exception:
                self._time = None
        if self._time is not None:
            try:
                self._armed_at_ms = self._time.ticks_ms()
            except Exception:
                self._armed_at_ms = None
        return True

    def _clear_streak_if_healthy(self):
        if (self._healthy_checked or not self.reset_count or
                self._armed_at_ms is None):
            return
        try:
            elapsed_ms = self._time.ticks_diff(
                self._time.ticks_ms(), self._armed_at_ms
            )
        except Exception:
            return
        if elapsed_ms < _HEALTHY_RUNTIME_MS:
            return
        self._healthy_checked = True
        if self._write_reset_count(0):
            self.reset_count = 0

    def feed(self):
        if self._wdt is None:
            return False
        try:
            self._wdt.feed()
        except Exception as error:
            self._logger("Unable to feed runtime watchdog: %s" % error)
            return False
        self._clear_streak_if_healthy()
        return True


def _configured_timeout(config_module, logger):
    try:
        timeout_ms = getattr(config_module, "WATCHDOG_TIMEOUT_MS")
    except AttributeError:
        return None

    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int):
        logger("WATCHDOG_TIMEOUT_MS ignored: expected an integer")
        return None
    if timeout_ms < _MIN_TIMEOUT_MS:
        logger("WATCHDOG_TIMEOUT_MS ignored: minimum is 5000 ms")
        return None
    return timeout_ms


def configure(config_module, machine_module=None, nvs=None,
              time_module=None, logger=None):
    """Configure, but do not start, the optional runtime watchdog."""
    global _active
    log = logger or print
    timeout_ms = _configured_timeout(config_module, log)
    if timeout_ms is not None and machine_module is None:
        try:
            import machine as machine_module
        except Exception as error:
            log("Runtime watchdog unavailable: %s" % error)
            timeout_ms = None
    if timeout_ms is not None and nvs is None:
        try:
            nvs = nvs_store.open_nvs(_NVS_NAMESPACE)
        except Exception as error:
            log("Watchdog reset counter unavailable: %s" % error)
    _active = RuntimeWatchdog(
        timeout_ms,
        machine_module=machine_module,
        nvs=nvs,
        time_module=time_module,
        logger=log,
    )
    _active.process_boot()
    return _active


def feed():
    if _active is None:
        return False
    return _active.feed()


def http_timeout_s():
    if _active is None or not _active.running:
        return None
    return _WATCHDOG_HTTP_TIMEOUT_S
