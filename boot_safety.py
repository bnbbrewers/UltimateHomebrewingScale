"""Minimal hardware safety actions that run before the normal runtime."""

_DEFAULT_RELAY_IO = (1, 2)


def force_relay_off(config_module=None, pin_type=None, logger=None):
    """Drive the keg relay control GPIO low as early as possible."""
    log = logger or print
    relay_io = getattr(config_module, "KEG_RELAY_IO", _DEFAULT_RELAY_IO)
    try:
        relay_pin = int(relay_io[1])
        if pin_type is None:
            from machine import Pin
            pin_type = Pin
        pin = pin_type(relay_pin)
        pin.init(mode=pin_type.OUT)
        pin(0)
        return True
    except Exception as error:
        log("Unable to force keg relay off: %s" % error)
        return False
