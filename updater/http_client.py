"""Updater facade for the shared, memory-bounded HTTP transport."""

import gc

try:
    import config as _config
    _DEBUG = bool(getattr(_config, "DEBUG", False))
except Exception:
    _DEBUG = False

try:
    from memory_debug import snapshot as _memory_snapshot
    from memory_debug import stats as _memory_stats
except Exception:
    _memory_snapshot = None
    _memory_stats = None

from network.http_transport import BodyTooLargeError
from network.http_transport import close_response
from network.http_transport import default_requests_module as _default_requests_module
from network.http_transport import gc_hard
from network.http_transport import get as _transport_get
from network.http_transport import load_json_file
from network.http_transport import remove_file
from network.http_transport import response_header
from network.http_transport import response_text
from network.http_transport import spool_response_to_file
from network.http_transport import ticks_diff
from network.http_transport import ticks_ms


REQUEST_TIMEOUT_S = 15
_requests = None


def default_requests_module():
    global _requests
    if _requests is not None:
        return _requests
    gc_hard(cycles=1, pause_ms=10)
    snapshot("updater.before_import_requests2")
    requests_module = _default_requests_module()
    snapshot("updater.after_import_requests2")
    _requests = requests_module
    return _requests


def debug_enabled():
    return _DEBUG


def stats(collect=False):
    if _memory_stats is not None:
        try:
            return _memory_stats(collect=collect)
        except Exception:
            pass
    try:
        return gc.mem_free(), None, None
    except Exception:
        return -1, None, None


def stats_text(collect=False):
    py_free, c_free, c_largest = stats(collect=collect)
    if c_free is None:
        return "py_free={}".format(py_free)
    return "py_free={} c_free={} c_largest={}".format(
        py_free, c_free, c_largest
    )


def snapshot(tag):
    if not _DEBUG:
        return
    if _memory_snapshot is not None:
        try:
            _memory_snapshot(tag, enabled=True, collect=False)
            return
        except Exception:
            pass
    try:
        print("[MEM] {} {}".format(tag, stats_text()))
    except Exception:
        pass


def debug_print(message):
    if _DEBUG:
        try:
            print(message)
        except Exception:
            pass


def get(requests_module, url, headers=None, stream=False,
        timeout_s=REQUEST_TIMEOUT_S):
    snapshot("updater.http.before_get")
    response = _transport_get(
        requests_module,
        url,
        headers=headers,
        stream=stream,
        timeout_s=timeout_s,
    )
    debug_print("[updater] HTTP GET {} {}".format(url, stats_text()))
    return response


def read_response_json(response, tmp_path, max_content_bytes=65536):
    remove_file(tmp_path)
    try:
        mode = spool_response_to_file(
            response,
            tmp_path,
            max_content_bytes=max_content_bytes,
        )
        debug_print("[updater] HTTP JSON spooled: mode={} {}".format(
            mode, stats_text()
        ))
        close_response(response)
        gc_hard(cycles=1, pause_ms=10)
        data = load_json_file(tmp_path)
        del mode
        gc_hard(cycles=1, pause_ms=10)
        return data
    finally:
        close_response(response)
        remove_file(tmp_path)
