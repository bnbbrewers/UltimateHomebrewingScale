"""Once per boot, find out whether a newer release exists.

The launcher calls tick() on every loop. Nothing happens until Wi-Fi is up
and the operator has left the launcher alone for a few seconds, because the
lookup blocks the UI: there is no thread on the Dial, and requests2 holds the
loop for the whole HTTPS call. Then one lookup runs, whatever its outcome,
and its result stays here for the rest of the boot.

Everything that can hurt the running app is bounded: the heap is checked
first (a Python heap that grows with Wi-Fi up takes the C block TLS needs),
the watchdog is fed around a single short attempt, and the updater modules
the lookup imported are evicted afterwards. A failure shows nothing.
"""

import gc
import sys

import runtime_debug

IDLE_BEFORE_CHECK_MS = 3000
MIN_PY_FREE = 45 * 1024
# The TLS handshake's largest allocation fits in 12 KB (firmware/CustomFirmware.MD).
MIN_C_LARGEST = 12 * 1024
FALLBACK_TIMEOUT_S = 10

# Imported for the lookup only; dropped again unless they were already loaded.
_EVICTABLE = (
    "updater.github_release",
    "updater.http_client",
    "netcore.http_transport",
    "requests2",
    "memory_debug",
)

_done = False
_available = None


def available():
    """None, or (installed, newer) release tags, e.g. ("v0.0.31", "v0.0.32")."""
    return _available


def reset():
    """Forget this boot's attempt. For tests."""
    global _done, _available
    _done = False
    _available = None


def tick(wifi, idle_ms):
    global _done
    if _done or wifi is None or idle_ms < IDLE_BEFORE_CHECK_MS:
        return
    connected = getattr(wifi, "connected", None)
    if connected is None or not connected():
        return
    # Spent before the lookup: an exception must never turn into a retry
    # that freezes the launcher again.
    _done = True
    try:
        _check()
    except Exception as e:
        runtime_debug.log("[update_notice] check failed: {!r}", e)


def _import(name):
    __import__(name)
    return sys.modules[name]


def _check():
    global _available
    before = set(sys.modules)
    try:
        if not _memory_ok():
            runtime_debug.log("[update_notice] skipped: low memory")
            return
        watchdog = _import("runtime_watchdog")
        boot = _import("updater.boot")
        version = _import("updater.version")
        github_release = _import("updater.github_release")
        timeout_s = watchdog.http_timeout_s() or FALLBACK_TIMEOUT_S
        watchdog.feed()
        try:
            release = github_release.resolve_release(
                boot.configured_channel(), retries=1, timeout_s=timeout_s
            )
        finally:
            watchdog.feed()
        local = version.read_local_version()
        remote = release.get("tag", "")
        if version.is_newer(remote, local):
            _available = (local, remote)
        runtime_debug.log("[update_notice] local={} remote={}", local, remote)
    finally:
        _evict(before)
        gc.collect()


def _memory_ok():
    stats = _import("memory_debug").stats
    py_free, _c_free, c_largest = stats(collect=True)
    if py_free < MIN_PY_FREE:
        return False
    # None off the device: the C heap cannot be read there.
    if c_largest is not None and c_largest < MIN_C_LARGEST:
        return False
    return True


def _evict(before):
    for name in _EVICTABLE:
        if name in before or name not in sys.modules:
            continue
        del sys.modules[name]
        parent, _, attr = name.rpartition(".")
        package = sys.modules.get(parent) if parent else None
        if package is not None:
            try:
                delattr(package, attr)
            except Exception:
                pass
