"""Minimal hardware safety actions that run before the normal runtime."""

_DEFAULT_RELAY_IO = (1, 2)


def _release_deep_sleep_hold(esp32_module, logger):
    """Standby pins the relay pad across deep sleep; a held pad stays held
    after the reboot, so the write below would otherwise reach nothing."""
    if esp32_module is None:
        try:
            import esp32 as esp32_module
        except Exception:
            return
    release = getattr(esp32_module, "gpio_deep_sleep_hold", None)
    if release is None:
        return
    try:
        release(False)
    except Exception as error:
        logger("Unable to release the deep sleep hold: %s" % error)


def force_relay_off(config_module=None, pin_type=None, logger=None,
                    esp32_module=None):
    """Drive the keg relay control GPIO low as early as possible."""
    log = logger or print
    relay_io = getattr(config_module, "KEG_RELAY_IO", _DEFAULT_RELAY_IO)
    _release_deep_sleep_hold(esp32_module, log)
    try:
        relay_pin = int(relay_io[1])
        if pin_type is None:
            from machine import Pin
            pin_type = Pin
        pin = pin_type(relay_pin)
        try:
            pin.init(mode=pin_type.OUT, hold=False)
        except TypeError:
            # Ports without per-pin hold support.
            pin.init(mode=pin_type.OUT)
        pin(0)
        return True
    except Exception as error:
        log("Unable to force keg relay off: %s" % error)
        return False
