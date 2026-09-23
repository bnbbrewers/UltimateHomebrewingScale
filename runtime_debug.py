"""Single source for the debug flag and the memory tracing helpers.

Leaf module on purpose: it imports `gc`, and `config`/`memory_debug` only
through the guards below. Every runtime module can pull it in without
disturbing import order or the heap layout, which is why the per-module
`try: import config` / `_collect_runtime` / `_mem_snapshot` preamble that used
to be copied into fifteen files now lives here once.

`memory_debug` is imported only when DEBUG is set, so a production build never
loads the tracing code at all.
"""

import gc

try:
    import config as _config
    DEBUG = bool(getattr(_config, "DEBUG", False))
except Exception:
    _config = None
    DEBUG = False

if DEBUG:
    try:
        from memory_debug import snapshot as _snapshot
    except Exception:
        _snapshot = None
else:
    _snapshot = None


def snapshot(tag, enabled=DEBUG, collect=False):
    """Trace a memory snapshot. A no-op unless DEBUG loaded memory_debug."""
    if enabled and _snapshot is not None:
        _snapshot(tag, enabled=True, collect=collect)


def collect(cycles=1):
    """Run the collector, more than once when a transition needs it."""
    for _ in range(cycles if cycles > 0 else 1):
        gc.collect()


def mem_free():
    """Free Python heap, or -1 on a host where gc.mem_free does not exist."""
    try:
        return gc.mem_free()
    except AttributeError:
        return -1


def log(message, *args):
    """Print under DEBUG only. Never raises: the console can be absent.

    Pass the format arguments rather than a formatted string: the string is
    then built only when DEBUG is on, so a production run allocates nothing
    for a trace it will not print.
    """
    if not DEBUG:
        return
    try:
        print(message.format(*args) if args else message)
    except Exception:
        pass


def safe(call, tag="", default=None):
    """Run `call`, swallow its failure, but leave a trace under DEBUG.

    The runtime has to tolerate optional hardware and MicroPython APIs that
    vary between firmwares, so failures are swallowed by design. Routing those
    through here keeps production behaviour identical while making the same
    failure visible when DEBUG is on.
    """
    try:
        return call()
    except Exception as error:
        if DEBUG:
            log("[safe] {} failed: {}".format(tag or "call", error))
        return default


def setting(name, default=None):
    """Read a config entry without caring whether config.py could be loaded."""
    if _config is None:
        return default
    return getattr(_config, name, default)
