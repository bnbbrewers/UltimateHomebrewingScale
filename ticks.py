"""MicroPython tick helpers with a CPython fallback.

Leaf module: `time` only. The bindings are resolved once at import instead of
probing `hasattr(time, "ticks_ms")` on every call, which matters in the keg
filling loop where these run on every iteration.

The fallback keeps app logic runnable on a desktop, where `time.ticks_*` does
not exist. Tick values are opaque: compare them with `ticks_diff`, never with
`<` or `-`, because they wrap on the device.
"""

import time

try:
    ticks_ms = time.ticks_ms
    ticks_add = time.ticks_add
    ticks_diff = time.ticks_diff
except AttributeError:
    def ticks_ms():
        return int(time.time() * 1000)

    def ticks_add(ticks, delta):
        return ticks + delta

    def ticks_diff(left, right):
        return left - right

try:
    sleep_ms = time.sleep_ms
except AttributeError:
    def sleep_ms(ms):
        time.sleep(ms / 1000.0)
