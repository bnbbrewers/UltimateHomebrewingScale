"""Setup portal service loaded by Settings.

The route dispatcher and HTML module are initialized before the QR screen is
created.  This avoids imports competing with the screen's remaining heap on
the M5Dial; actual HTML strings are still built only for a request.
"""

import time

PORTAL_HTTP_HOST = "0.0.0.0"
PORTAL_HTTP_PORT = 8080
AP_SETTLE_MS = 300
CLIENT_TIMEOUT_MS = 5000
RESPONSE_DRAIN_MS = 200
WRITE_CHUNK_SIZE = 256
MAX_WRITE_STEPS = 16

SETUP_AP_SSID = "UHS-Setup"
SETUP_AP_PASSWORD = ""
SETUP_REQUIRE_TOKEN = False
SETUP_TOKEN = ""

_EDITABLE_FIELDS = (
    ("LANGUAGE", "Language", "select", ("fr", "en")),
    ("WIFI_SSID", "Wi-Fi SSID", "text", ()),
    ("WIFI_PASSWORD", "Wi-Fi password", "password", ()),
    ("BREWING_SOFTWARE", "Brewing software", "select", ("brewfather",)),
    ("BREWFATHER_USER_ID", "Brewfather user id", "text", ()),
    ("BREWFATHER_API_KEY", "Brewfather API key", "password", ()),
    ("GRAIN_WEIGHT_TOLERANCE", "Grain tolerance (g)", "number", ()),
    ("HOP_WEIGHT_TOLERANCE", "Hop tolerance (g)", "number", ()),
    ("KEG_SPUNDING_VALVE_INERTIA_ML", "Spunding inertia (ml)", "number", ()),
    ("DEBUG", "Debug mode", "checkbox", ()),
    ("UPDATE_CHANNEL", "Release channel", "select", ("stable", "prerelease")),
)


INITIAL_PAGE_SERVED = "INITIAL_PAGE_SERVED"


def _load_setup_cfg():
    return {
        "ap_ssid": SETUP_AP_SSID,
        "ap_password": SETUP_AP_PASSWORD,
        "require_token": bool(SETUP_REQUIRE_TOKEN),
        "token": str(SETUP_TOKEN or ""),
    }


def build_portal_url(sta_ip=None, ap_ip=None, port=PORTAL_HTTP_PORT, token=""):
    ip = sta_ip or ap_ip or "192.168.4.1"
    url = "http://{}:{}/".format(ip, int(port))
    if token:
        url += "?k={}".format(token)
    return url


def _sleep_ms(ms):
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(ms)
    else:
        time.sleep(ms / 1000.0)


def _ticks_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.time() * 1000)


def _ticks_add(ticks, delta):
    if hasattr(time, "ticks_add"):
        return time.ticks_add(ticks, delta)
    return ticks + delta


def _ticks_diff(ticks1, ticks2):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(ticks1, ticks2)
    return ticks1 - ticks2


def _is_transient_socket_error(exc):
    try:
        return int(getattr(exc, "errno", exc.args[0])) in (11, 35, 110, 116)
    except Exception:
        return False


def _set_client_nonblocking(client):
    try:
        client.setblocking(False)
        return True
    except Exception:
        try:
            client.settimeout(0)
            return True
        except Exception:
            return False


def _url_decode(text):
    s = (text or "").replace("+", " ")
    out = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "%" and i + 2 < n:
            try:
                out.append(chr(int(s[i + 1 : i + 3], 16)))
                i += 3
                continue
            except Exception:
                pass
        out.append(ch)
        i += 1
    return "".join(out)


def parse_form_urlencoded(body):
    payload = {}
    if not body:
        return payload
    for pair in body.split("&"):
        if not pair:
            continue
        if "=" in pair:
            k, v = pair.split("=", 1)
        else:
            k, v = pair, ""
        payload[_url_decode(k)] = _url_decode(v)
    return payload


def _split_target(target):
    if "?" in target:
        path, query = target.split("?", 1)
    else:
        path, query = target, ""
    return path, parse_form_urlencoded(query)


def _portal_content():
    return __import__("webportal.portal_html", None, None, ("*",))


def render_minimal_form_html(values, saved=False, error="", kegs=None, i18n=None):
    return _portal_content().render_form_html(
        values,
        kegs=kegs or [],
        include_kegs=kegs is not None,
        error=error,
        i18n=i18n,
    )


def render_kegs_html(kegs, i18n=None):
    return _portal_content().render_form_html({}, kegs=kegs or [], include_kegs=True, i18n=i18n)


def _current_values():
    try:
        from storage import config_registry
        return config_registry.load_current_values()
    except Exception:
        values = {}
        try:
            import config
        except Exception:
            config = None
        for key, _label, typ, choices in _EDITABLE_FIELDS:
            if typ == "checkbox":
                default = False
            elif typ == "select" and choices:
                default = choices[0]
            elif typ == "number":
                default = 0
            else:
                default = ""
            values[key] = getattr(config, key, default) if config else default
        return values


def _load_kegs():
    try:
        from storage import keg_registry
        return keg_registry.load_kegs()
    except Exception:
        return []


def _kegs_from_form(kegs, form):
    return _portal_content().kegs_from_form(kegs, form)


class SetupPortalService:
    def __init__(self, wifi_device=None, debug=False, i18n=None, before_client=None):
        # Load the small route dispatcher while Settings is being created.
        # Delaying this import until the first browser request is too late on
        # M5Dial: the QR screen has then consumed the remaining C heap.
        from webportal.portal_routes import handle_request
        _portal_content()

        self._wifi = wifi_device
        self._debug = bool(debug)
        self._i18n = i18n
        self._before_client = before_client
        self._cfg = _load_setup_cfg()
        self._listener = None
        self._mode = "none"
        self._paused = False
        self._sta_ip = ""
        self._ap_ip = ""
        self._url = ""
        self._ap = None
        self._events = []
        self._initial_page_served = False
        self._before_client_ran = False
        self._client = None
        self._client_state = "idle"
        self._request_data = b""
        self._request_header_end = -1
        self._request_content_length = 0
        self._request_method = ""
        self._request_target = ""
        self._request_body = ""
        self._response_data = b""
        self._response_offset = 0
        self._response_is_initial_page = False
        self._client_deadline = 0
        self._handle_request = handle_request

        self._token = self._cfg.get("token", "")
        if self._cfg.get("require_token") and not self._token:
            try:
                self._token = str(time.ticks_ms())
            except Exception:
                self._token = "setup"

    def _log(self, *args):
        if not self._debug:
            return
        try:
            print("[portal]", *args)
        except Exception:
            pass

    def start_or_resume(self):
        self._paused = False
        self._log("start_or_resume begin")
        self._ensure_network()
        self._log("network mode={} sta_ip={} ap_ip={} url={}".format(
            self._mode,
            self._sta_ip,
            self._ap_ip,
            self._url,
        ))
        self._start_server_if_needed()
        self._log("start_or_resume ready listener={}".format(self._listener is not None))
        return self.info()

    def info(self):
        return {
            "mode": self._mode,
            "sta_ip": self._sta_ip,
            "ap_ip": self._ap_ip,
            "url": self._url,
            "ap_ssid": self._cfg.get("ap_ssid", ""),
            "ap_password": self._cfg.get("ap_password", ""),
        }

    def stop(self):
        self._paused = True
        self._close_client()
        listener = self._listener
        self._listener = None
        if listener:
            try:
                listener.settimeout(0)
            except Exception:
                pass
            try:
                listener.close()
            except Exception:
                pass
        ap = self._ap
        self._ap = None
        if ap:
            try:
                ap.active(False)
            except Exception:
                pass

    def suspend(self):
        self._paused = True

    def consume_events(self):
        events = tuple(self._events)
        self._events = []
        return events

    def tick(self):
        if self._paused or not self._listener:
            return
        if self._client is None:
            try:
                client, addr = self._listener.accept()
            except Exception:
                return
            self._client = client
            self._client_state = "read"
            self._request_data = b""
            self._request_header_end = -1
            self._request_content_length = 0
            self._response_data = b""
            self._response_offset = 0
            self._response_is_initial_page = False
            self._client_deadline = _ticks_add(_ticks_ms(), CLIENT_TIMEOUT_MS)
            if not _set_client_nonblocking(client):
                self._log("client nonblocking setup failed")
                self._close_client()
                return
            self._log("client nonblocking")
            self._log("accept", addr)

        try:
            if self._client_state == "read":
                self._progress_read()
            if self._client_state == "write":
                self._progress_write()
            if self._client_state == "drain":
                if _ticks_diff(self._client_deadline, _ticks_ms()) <= 0:
                    self._log("response drain complete")
                    self._close_client()
        except Exception as e:
            self._log("client error:", e)
            self._close_client()

    def _close_client(self):
        client = self._client
        self._client = None
        self._client_state = "idle"
        self._response_data = b""
        self._response_offset = 0
        if client:
            try:
                client.close()
                self._log("client closed")
            except Exception:
                pass

    def _progress_read(self):
        client = self._client
        try:
            chunk = client.recv(1024)
        except Exception as e:
            if _is_transient_socket_error(e):
                if _ticks_diff(self._client_deadline, _ticks_ms()) > 0:
                    return
            self._log("recv header error", type(e).__name__, e)
            self._close_client()
            return
        if not chunk:
            self._log("request eof bytes", len(self._request_data))
            self._close_client()
            return

        self._request_data += chunk
        self._log("recv request chunk", len(chunk), "total", len(self._request_data))
        if self._request_header_end < 0:
            marker = self._request_data.find(b"\r\n\r\n")
            marker_len = 4
            if marker < 0:
                marker = self._request_data.find(b"\n\n")
                marker_len = 2
            if marker < 0:
                if len(self._request_data) >= 4096:
                    self._log("request too large")
                    self._close_client()
                return
            self._request_header_end = marker + marker_len
            head = self._request_data[:marker]
            self._parse_request_head(head)

        body = self._request_data[self._request_header_end :]
        if len(body) < self._request_content_length:
            return
        self._request_body = body[: self._request_content_length].decode("utf-8", "replace")
        method = self._request_method
        target = self._request_target
        if not method:
            self._log("empty request")
            self._close_client()
            return
        self._log("request ready", method, target, "body", len(self._request_body))
        if self._request_needs_screen_memory(method, target):
            self._run_before_client()
        self._response_is_initial_page = method == "GET" and _split_target(target)[0] == "/"
        self._handle_request(self, self._client, method, target, self._request_body)
        self._client_state = "write"
        self._client_deadline = _ticks_add(_ticks_ms(), CLIENT_TIMEOUT_MS)

    def _parse_request_head(self, head):
        try:
            head_text = head.decode("utf-8")
        except Exception:
            head_text = head.decode("latin-1")
        lines = [ln for ln in head_text.replace("\r\n", "\n").split("\n") if ln]
        parts = (lines[0] if lines else "").split(" ")
        self._request_method = parts[0] if len(parts) > 0 else ""
        self._request_target = parts[1] if len(parts) > 1 else "/"
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        try:
            self._request_content_length = int(headers.get("content-length", "0") or "0")
        except Exception:
            self._request_content_length = 0
        self._log(
            "request",
            self._request_method,
            self._request_target,
            "head",
            len(head),
            "ua",
            headers.get("user-agent", "")[:40],
            "conn",
            headers.get("connection", ""),
        )

    def _progress_write(self):
        client = self._client
        if not self._response_data:
            self._close_client()
            return
        steps = 0
        while self._response_offset < len(self._response_data) and steps < MAX_WRITE_STEPS:
            end = min(self._response_offset + WRITE_CHUNK_SIZE, len(self._response_data))
            try:
                sent = client.write(self._response_data[self._response_offset : end])
            except Exception as e:
                if _is_transient_socket_error(e) and _ticks_diff(self._client_deadline, _ticks_ms()) > 0:
                    self._log("write pending", type(e).__name__, e, "offset", self._response_offset)
                    return
                self._log("write error", type(e).__name__, e, "offset", self._response_offset)
                self._close_client()
                return
            if sent is None or sent <= 0:
                if _ticks_diff(self._client_deadline, _ticks_ms()) <= 0:
                    self._log("write timeout", "offset", self._response_offset)
                    self._close_client()
                return
            self._response_offset += sent
            steps += 1
            self._log("write chunk", sent, "offset", self._response_offset, "size", len(self._response_data))
        if self._response_offset >= len(self._response_data):
            self._log("response sent")
            if self._response_is_initial_page and not self._initial_page_served:
                self._initial_page_served = True
                self._events.append(INITIAL_PAGE_SERVED)
                self._log("event", INITIAL_PAGE_SERVED)
            # M5UI's socket write can return after copying data to the TCP
            # buffer.  Keep the nonblocking client alive briefly so the stack
            # can emit the FIN after the response bytes have drained.
            self._client_state = "drain"
            self._client_deadline = _ticks_add(_ticks_ms(), RESPONSE_DRAIN_MS)
            self._log("response drain", RESPONSE_DRAIN_MS)

    def _run_before_client(self):
        if self._before_client_ran:
            self._log("cleanup skip already_ran")
            return
        self._before_client_ran = True
        callback = self._before_client
        if callback is None:
            self._log("cleanup skip no_callback")
            return
        try:
            self._log("cleanup begin")
            callback()
            self._log("cleanup done")
        except Exception as e:
            self._log("before client cleanup error:", e)
        try:
            import gc

            gc.collect()
            gc.collect()
        except Exception:
            pass

    @staticmethod
    def _request_needs_screen_memory(method, target):
        path, query = _split_target(target)
        if query.get("nocleanup") == "1":
            return False
        if path in ("/health", "/diag", "/favicon.ico"):
            return False
        return True

    def _ensure_network(self):
        self._cfg = _load_setup_cfg()
        sta_ip = self._try_sta()
        if sta_ip:
            self._mode = "sta"
            self._sta_ip = sta_ip
            self._ap_ip = ""
            self._url = build_portal_url(sta_ip=sta_ip, port=PORTAL_HTTP_PORT, token=self._token if self._cfg.get("require_token") else "")
            return

        ap_ip = self._ensure_ap()
        self._mode = "ap"
        self._sta_ip = ""
        self._ap_ip = ap_ip
        self._url = build_portal_url(ap_ip=ap_ip, port=PORTAL_HTTP_PORT, token=self._token if self._cfg.get("require_token") else "")

    def _try_sta(self):
        try:
            import network

            sta = network.WLAN(network.STA_IF)
            if sta.isconnected():
                return sta.ifconfig()[0]
        except Exception:
            pass

        if self._wifi:
            try:
                if self._wifi.ensure_connected(timeout_s=3):
                    wlan = getattr(self._wifi, "_wlan", None)
                    if wlan and wlan.isconnected():
                        return wlan.ifconfig()[0]
            except Exception:
                pass
        return ""

    def _ensure_ap(self):
        try:
            import network

            ap = network.WLAN(network.AP_IF)
            if not ap.active():
                ap.active(True)
            self._ap = ap
            ssid = self._cfg.get("ap_ssid", "UHB-Scale-Setup")
            password = self._cfg.get("ap_password", "")
            if password and len(password) >= 8:
                try:
                    ap.config(essid=ssid, password=password)
                except Exception:
                    try:
                        ap.config(essid=ssid, authmode=network.AUTH_WPA_WPA2_PSK, password=password)
                    except Exception:
                        pass
            else:
                try:
                    ap.config(essid=ssid)
                except Exception:
                    pass
            _sleep_ms(AP_SETTLE_MS)
            try:
                return ap.ifconfig()[0]
            except Exception:
                return "192.168.4.1"
        except Exception:
            return "192.168.4.1"

    def _start_server_if_needed(self):
        if self._listener:
            return
        import socket

        last = None
        for attempt in range(1, 4):
            s = None
            try:
                try:
                    import gc

                    gc.collect()
                except Exception:
                    pass
                self._log("listen socket create")
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._log("listen socket created")
                try:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self._log("listen reuseaddr ok")
                except Exception:
                    self._log("listen reuseaddr unsupported")
                self._log("listen bind begin", PORTAL_HTTP_HOST, PORTAL_HTTP_PORT)
                s.bind((PORTAL_HTTP_HOST, PORTAL_HTTP_PORT))
                self._log("listen bind ok")
                s.listen(1)
                self._log("listen backlog ok")
                s.settimeout(0)
                self._log("listen nonblocking ok")
                self._listener = s
                self._log("listen ok attempt", attempt)
                return
            except Exception as e:
                last = e
                self._log("listen fail attempt {}: {}".format(attempt, e))
                if s is not None:
                    try:
                        s.close()
                    except Exception:
                        pass
                time.sleep_ms(80)
        if last is not None:
            raise last

    def _send(self, client, status_code=200, content_type="text/plain; charset=utf-8", body="", headers=None):
        status_txt = {
            200: "OK",
            303: "See Other",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found",
            500: "Internal Server Error",
        }.get(status_code, "OK")
        payload = body.encode("utf-8") if isinstance(body, str) else body
        lines = [
            "HTTP/1.1 {} {}".format(status_code, status_txt),
            "Content-Type: {}".format(content_type),
            "Content-Length: {}".format(len(payload)),
            "Connection: close",
        ]
        lines.append("Cache-Control: no-store")
        if headers:
            for k, v in headers.items():
                lines.append("{}: {}".format(k, v))
        lines.append("")
        lines.append("")
        head = "\r\n".join(lines).encode("utf-8")
        self._log("response", status_code, "head", len(head), "body", len(payload))
        self._response_data = head + payload
        self._response_offset = 0

    def _token_ok(self, query, form):
        if not self._cfg.get("require_token"):
            return True
        return (query.get("k") or form.get("k") or "") == self._token
