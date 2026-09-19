"""
Relay control for the keg filler valve.
"""

import runtime_debug

DEFAULT_RELAY_IO = runtime_debug.setting("KEG_RELAY_IO", (1, 2))


def _debug(message):
    runtime_debug.log("[Relay] {}", message)


class RelayDevice:
    """
    Safe relay abstraction.
    Defaults to software-only state when physical relay is unavailable.
    """

    def __init__(self, io=None):
        self._state = False
        self._relay = None
        self._last_error = None
        self._io = io if io is not None else DEFAULT_RELAY_IO
        self._init_relay(self._io)
        self.set_off()

    def _init_relay(self, io):
        _debug("init io={}".format(io))
        try:
            from unit import RelayUnit
            self._relay = RelayUnit(io)
            self._last_error = None
            _debug("ready")
        except Exception as e:
            self._relay = None
            self._last_error = str(e)
            _debug("unavailable: {}".format(self._last_error))

    def set_on(self):
        self._state = True
        _debug("on")
        if self._relay:
            try:
                self._relay.on()
            except Exception as e:
                runtime_debug.log("Relay on failed: {}", e)

    def set_off(self):
        self._state = False
        _debug("off")
        if self._relay:
            try:
                self._relay.off()
            except Exception as e:
                runtime_debug.log("Relay off failed: {}", e)

    def is_on(self):
        if self._relay and hasattr(self._relay, "get_status"):
            try:
                return bool(self._relay.get_status())
            except Exception:
                pass
        return self._state

    def is_available(self):
        return self._relay is not None

    def last_error(self):
        return self._last_error
