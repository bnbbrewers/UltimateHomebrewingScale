"""Small, dependency-free HTTP transport helpers.

This package stays independent from ``core`` so importing the updater does not
load the LVGL runtime at boot.
"""

import gc
import os
import time


REQUEST_TIMEOUT_S = 15
_requests = None


class BodyTooLargeError(RuntimeError):
    """The non-streaming response fallback exceeded its configured bound."""


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


def default_requests_module():
    global _requests
    if _requests is not None:
        return _requests
    try:
        import requests2
        _requests = requests2
    except Exception:
        _requests = None
    return _requests


def create_session(requests_module):
    """Create one optional requests2 session without making it mandatory."""
    if requests_module is None:
        return None
    factory = getattr(requests_module, "Session", None)
    if factory is None:
        return None
    try:
        return factory()
    except Exception:
        return None


def close_session(session):
    if session is None:
        return
    close = getattr(session, "close", None)
    if close is not None:
        try:
            close()
        except Exception:
            pass


def _request_variants(headers, stream, timeout_s):
    kwargs = {}
    if headers is not None:
        kwargs["headers"] = headers
    if stream:
        kwargs["stream"] = True
    if timeout_s:
        kwargs["timeout"] = timeout_s

    variants = [kwargs]
    if "timeout" in kwargs:
        no_timeout = dict(kwargs)
        del no_timeout["timeout"]
        variants.append(no_timeout)
    if "stream" in kwargs:
        no_stream = dict(kwargs)
        del no_stream["stream"]
        variants.append(no_stream)
        if "timeout" in no_stream:
            no_stream_no_timeout = dict(no_stream)
            del no_stream_no_timeout["timeout"]
            variants.append(no_stream_no_timeout)
    return variants


def get(requests_module, url, headers=None, stream=False,
        timeout_s=REQUEST_TIMEOUT_S):
    """Perform one GET while tolerating requests2 API differences."""
    last_error = None
    for attempt in _request_variants(headers, stream, timeout_s):
        try:
            return requests_module.get(url, **attempt)
        except TypeError as error:
            last_error = error
    if last_error is not None:
        raise last_error
    raise RuntimeError("HTTP request could not be created")


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


def response_text(response):
    text = getattr(response, "text", None)
    if text:
        return text
    content = getattr(response, "content", None)
    if content:
        try:
            return content.decode("utf-8")
        except Exception:
            return str(content)
    return ""


def close_response(response):
    if response is None:
        return
    try:
        response.close()
    except Exception:
        pass
    raw = getattr(response, "raw", None)
    if raw is not None:
        close = getattr(raw, "close", None)
        if close is not None:
            try:
                close()
            except Exception:
                pass


def remove_file(path):
    try:
        os.remove(path)
    except Exception:
        pass


def _check_size(total, max_content_bytes):
    if (max_content_bytes is not None and
            total > int(max_content_bytes)):
        raise BodyTooLargeError("HTTP body exceeds {} bytes".format(
            max_content_bytes))


def spool_response_to_file(response, path, max_content_bytes=None,
                           require_stream=False):
    """Write a response incrementally, with a bounded compatibility fallback."""
    with open(path, "wb") as output:
        total = 0
        raw = getattr(response, "raw", None)
        if raw is not None and hasattr(raw, "read"):
            while True:
                chunk = raw.read(512)
                if not chunk:
                    break
                total += len(chunk)
                _check_size(total, max_content_bytes)
                output.write(chunk)
                del chunk
            return "raw"

        iter_content = getattr(response, "iter_content", None)
        if iter_content:
            for chunk in iter_content(512):
                if chunk:
                    total += len(chunk)
                    _check_size(total, max_content_bytes)
                    output.write(chunk)
                del chunk
            return "iter"

        if require_stream:
            raise RuntimeError("HTTP response does not support streaming")

        content = getattr(response, "content", None)
        if content:
            total = len(content)
            _check_size(total, max_content_bytes)
            output.write(content)
            del content
            return "content"

        text = response_text(response)
        if text:
            encoded = text.encode("utf-8")
            del text
            total = len(encoded)
            _check_size(total, max_content_bytes)
            output.write(encoded)
            del encoded
            return "text"
    return "empty"


def load_json_file(path):
    import json

    with open(path, "r") as source:
        load = getattr(json, "load", None)
        if load:
            return load(source)
        return json.loads(source.read())


def read_response_json(response, tmp_path, max_content_bytes=65536):
    remove_file(tmp_path)
    try:
        spool_response_to_file(
            response, tmp_path, max_content_bytes=max_content_bytes
        )
        close_response(response)
        gc_hard(cycles=1, pause_ms=10)
        return load_json_file(tmp_path)
    finally:
        close_response(response)
        remove_file(tmp_path)
