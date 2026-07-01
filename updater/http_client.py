import gc
import os
import time

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


REQUEST_TIMEOUT_S = 15
_requests = None


def default_requests_module():
    global _requests
    if _requests is not None:
        return _requests
    gc_hard(cycles=1, pause_ms=10)
    snapshot("updater.before_import_requests2")
    try:
        import requests2 as requests_module
    except Exception:
        requests_module = None
    snapshot("updater.after_import_requests2")
    _requests = requests_module
    return _requests


def debug_enabled():
    return bool(_DEBUG)


def stats(collect=False):
    if _memory_stats is not None:
        try:
            return _memory_stats(collect=collect)
        except Exception:
            pass
    try:
        py_free = gc.mem_free()
    except Exception:
        py_free = -1
    return py_free, None, None


def stats_text(collect=False):
    py_free, c_free, c_largest = stats(collect=collect)
    if c_free is None:
        return "py_free={}".format(py_free)
    return "py_free={} c_free={} c_largest={}".format(py_free, c_free, c_largest)


def snapshot(tag):
    if not debug_enabled():
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


def gc_hard(cycles=2, pause_ms=20):
    for _ in range(cycles):
        gc.collect()
        try:
            time.sleep_ms(pause_ms)
        except Exception:
            time.sleep(pause_ms / 1000.0)


def ticks_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.time() * 1000)


def ticks_diff(a, b):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(a, b)
    return a - b


def debug_print(message):
    if not debug_enabled():
        return
    try:
        print(message)
    except Exception:
        pass


def errno_value(err):
    value = getattr(err, "errno", None)
    if value is not None:
        return value
    try:
        if err.args:
            return err.args[0]
    except Exception:
        pass
    return "n/a"


def request_options_text(kwargs):
    return "headers={} stream={} timeout={}".format(
        "yes" if "headers" in kwargs else "no",
        "yes" if kwargs.get("stream") else "no",
        kwargs.get("timeout", "none"),
    )


def get(requests_module, url, headers=None, stream=False, timeout_s=REQUEST_TIMEOUT_S):
    kwargs = {}
    if headers is not None:
        kwargs["headers"] = headers
    if stream:
        kwargs["stream"] = True
    if timeout_s:
        kwargs["timeout"] = timeout_s

    attempts = [kwargs]
    if "timeout" in kwargs:
        no_timeout = dict(kwargs)
        del no_timeout["timeout"]
        attempts.append(no_timeout)
    if "stream" in kwargs:
        no_stream = dict(kwargs)
        del no_stream["stream"]
        attempts.append(no_stream)
        if "timeout" in no_stream:
            no_stream_no_timeout = dict(no_stream)
            del no_stream_no_timeout["timeout"]
            attempts.append(no_stream_no_timeout)

    last_err = None
    total = len(attempts)
    for index, attempt_kwargs in enumerate(attempts, 1):
        mem_before = stats_text()
        gc_hard(cycles=1, pause_ms=10)
        mem_after_gc = stats_text()
        debug_print(
            "[updater] HTTP GET begin: variant={}/{} {} mem_before={} mem_after_gc={} url={}".format(
                index,
                total,
                request_options_text(attempt_kwargs),
                mem_before,
                mem_after_gc,
                url,
            )
        )
        start = ticks_ms()
        try:
            snapshot("updater.http.before_get")
            response = requests_module.get(url, **attempt_kwargs)
            debug_print(
                "[updater] HTTP GET end: variant={}/{} duration_ms={} mem_after={} url={}".format(
                    index,
                    total,
                    ticks_diff(ticks_ms(), start),
                    stats_text(),
                    url,
                )
            )
            return response
        except TypeError as e:
            last_err = e
            debug_print(
                "[updater] HTTP GET unsupported args: variant={}/{} duration_ms={} errno={} args={} {} url={}".format(
                    index,
                    total,
                    ticks_diff(ticks_ms(), start),
                    errno_value(e),
                    getattr(e, "args", ()),
                    request_options_text(attempt_kwargs),
                    url,
                )
            )
        except OSError as e:
            debug_print(
                "[updater] HTTP GET error: variant={}/{} duration_ms={} errno={} args={} mem_after={} {} url={}".format(
                    index,
                    total,
                    ticks_diff(ticks_ms(), start),
                    errno_value(e),
                    getattr(e, "args", ()),
                    stats_text(),
                    request_options_text(attempt_kwargs),
                    url,
                )
            )
            raise
    raise last_err


def response_text(response):
    text = getattr(response, "text", None)
    if text:
        return text
    content = getattr(response, "content", None)
    if content:
        try:
            return content.decode("utf-8")
        except Exception:
            try:
                return str(content)
            except Exception:
                pass
    return ""


def response_header(response, name):
    headers = getattr(response, "headers", None)
    if not headers:
        return ""
    try:
        value = headers.get(name, "")
        if value:
            return value
    except Exception:
        pass
    try:
        return headers.get(name.lower(), "")
    except Exception:
        return ""


def remove_file(path):
    try:
        os.remove(path)
    except Exception:
        pass


def spool_response_to_file(response, path):
    with open(path, "wb") as f:
        raw = getattr(response, "raw", None)
        if raw is not None and hasattr(raw, "read"):
            while True:
                chunk = raw.read(512)
                if not chunk:
                    break
                f.write(chunk)
                del chunk
            return "raw"

        iter_content = getattr(response, "iter_content", None)
        if iter_content:
            for chunk in iter_content(512):
                if chunk:
                    f.write(chunk)
                del chunk
            return "iter"

        content = getattr(response, "content", None)
        if content:
            f.write(content)
            del content
            return "content"

        text = response_text(response)
        if text:
            try:
                f.write(text.encode("utf-8"))
            except Exception:
                f.write(text)
            del text
            return "text"
    return "empty"


def load_json_file(path):
    import json

    with open(path, "r") as f:
        load = getattr(json, "load", None)
        if load:
            return load(f)
        return json.loads(f.read())


def read_response_json(response, tmp_path):
    remove_file(tmp_path)
    try:
        mode = spool_response_to_file(response, tmp_path)
        debug_print("[updater] HTTP JSON spooled: mode={} {}".format(mode, stats_text()))
        try:
            response.close()
        except Exception:
            pass
        gc_hard(cycles=1, pause_ms=10)
        data = load_json_file(tmp_path)
        del mode
        gc_hard(cycles=1, pause_ms=10)
        return data
    finally:
        remove_file(tmp_path)
