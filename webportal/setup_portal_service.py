"""Minimal setup portal service loaded by Settings.

The full form renderer/router stays in setup_portal.py and is imported only
when a browser actually connects. Entering Settings only needs networking.
"""

import time

PORTAL_HTTP_HOST = "0.0.0.0"
PORTAL_HTTP_PORT = 8080
AP_SETTLE_MS = 300
RESPONSE_DRAIN_MS = 200
SEND_CHUNK_SIZE = 256
SEND_YIELD_MS = 5

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
    ("UPDATE_BRANCH", "Update branch", "text", ()),
)


class _SendTimeout(Exception):
    pass


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


def _sleep_ms(ms):
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(ms)
    else:
        time.sleep(ms / 1000.0)


def _html_escape(text):
    s = str(text)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


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


def _current_values():
    try:
        from storage import config_registry

        return config_registry.load_current_values()
    except Exception:
        pass

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
        try:
            values[key] = getattr(config, key, default) if config else default
        except Exception:
            values[key] = default
    return values


def render_minimal_form_html(values, saved=False, error=""):
    p = []
    p.append("<!doctype html><html><head><meta charset='utf-8'>")
    p.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    p.append("<title>UHS setup</title></head><body><h3>UHS setup</h3>")
    if saved:
        p.append("<p><b>Saved. Rebooting...</b></p>")
    if error:
        p.append("<p><b>{}</b></p>".format(_html_escape(error)))
    p.append("<form method='post' action='/save'>")
    for key, label, typ, choices in _EDITABLE_FIELDS:
        val = values.get(key, "")
        p.append("<p>{}<br>".format(_html_escape(label)))
        if typ == "select":
            p.append("<select name='{}'>".format(key))
            for choice in choices:
                sel = " selected" if str(val) == str(choice) else ""
                p.append("<option value='{0}'{1}>{0}</option>".format(_html_escape(choice), sel))
            p.append("</select>")
        elif typ == "checkbox":
            checked = " checked" if bool(val) else ""
            p.append("<input type='checkbox' name='{}' value='on'{}>".format(key, checked))
        else:
            p.append("<input type='{0}' name='{1}' value='{2}'>".format(typ, key, _html_escape(val)))
        p.append("</p>")
    p.append("<p><button type='submit'>Save and reboot</button></p></form>")
    p.append("<form method='post' action='/update'><p><button type='submit'>UPDATE APP</button></p></form>")
    p.append("</body></html>")
    return "".join(p)


class SetupPortalService:
    def __init__(self, wifi_device=None, debug=False, i18n=None, before_client=None):
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
        self._before_client_ran = False

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
        self._ensure_network()
        self._start_server_if_needed()
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

    def tick(self):
        if self._paused or not self._listener:
            return
        try:
            client, addr = self._listener.accept()
        except Exception:
            return
        self._log("accept", addr)
        try:
            method, target, _headers, body = self._read_request(client)
            if not method:
                self._log("empty request")
                return
            if self._request_needs_screen_memory(method, target):
                self._run_before_client()
            self._handle_request(client, method, target, body)
        except _SendTimeout as e:
            self._log("client send failed:", e)
        except Exception as e:
            self._log("client error:", e)
            try:
                self._send(client, 500, "text/plain; charset=utf-8", "Internal error")
            except Exception:
                pass
        try:
            client.close()
            self._log("client closed")
        except Exception:
            pass
        try:
            import gc

            gc.collect()
        except Exception:
            pass

    def _run_before_client(self):
        if self._before_client_ran:
            return
        self._before_client_ran = True
        callback = self._before_client
        if callback is None:
            return
        try:
            callback()
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
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                except Exception:
                    pass
                s.bind((PORTAL_HTTP_HOST, PORTAL_HTTP_PORT))
                s.listen(1)
                s.settimeout(0)
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

    def _read_request(self, client):
        try:
            client.settimeout(3)
        except Exception:
            pass
        data = b""
        recv_count = 0
        while b"\r\n\r\n" not in data and len(data) < 4096:
            try:
                chunk = client.recv(1024)
            except Exception as e:
                self._log("recv header error", type(e).__name__, e)
                break
            if not chunk:
                self._log("recv header eof bytes", len(data), "reads", recv_count)
                break
            recv_count += 1
            self._log("recv header chunk", len(chunk), "total", len(data) + len(chunk))
            data += chunk
        head, sep, tail = data.partition(b"\r\n\r\n")
        if not sep:
            head, sep, tail = data.partition(b"\n\n")
        if not sep:
            self._log("request incomplete bytes", len(data))
            return "", "", {}, ""
        try:
            head_text = head.decode("utf-8")
        except Exception:
            head_text = head.decode("latin-1")

        lines = [ln for ln in head_text.replace("\r\n", "\n").split("\n") if ln]
        parts = (lines[0] if lines else "").split(" ")
        method = parts[0] if len(parts) > 0 else ""
        target = parts[1] if len(parts) > 1 else "/"
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        self._log(
            "request",
            method,
            target,
            "head",
            len(head),
            "tail",
            len(tail),
            "ua",
            headers.get("user-agent", "")[:40],
            "conn",
            headers.get("connection", ""),
        )
        body = tail
        content_length = 0
        try:
            content_length = int(headers.get("content-length", "0") or "0")
        except Exception:
            content_length = 0
        while len(body) < content_length and len(body) < 4096:
            try:
                chunk = client.recv(min(512, content_length - len(body)))
            except Exception as e:
                self._log("recv body error", type(e).__name__, e)
                break
            if not chunk:
                self._log("recv body eof bytes", len(body), "expected", content_length)
                break
            body += chunk
            self._log("recv body chunk", len(chunk), "total", len(body), "expected", content_length)
        try:
            body_text = body.decode("utf-8")
        except Exception:
            body_text = body.decode("latin-1")
        return method, target, headers, body_text

    def _send(self, client, status_code=200, content_type="text/plain; charset=utf-8", body="", headers=None):
        try:
            client.setblocking(True)
        except Exception:
            pass
        try:
            client.settimeout(3)
        except Exception:
            pass
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
        self._send_all(client, head)
        self._send_all(client, payload)
        self._log("response sent", status_code)
        self._log("response drain", RESPONSE_DRAIN_MS)
        _sleep_ms(RESPONSE_DRAIN_MS)

    def _send_all(self, client, data):
        if not data:
            return
        total = 0
        deadline = _ticks_add(_ticks_ms(), 3000)
        size = len(data)
        while total < size:
            sent = 0
            try:
                next_len = min(SEND_CHUNK_SIZE, size - total)
                self._log("send attempt", next_len, "offset", total, "size", size)
                sent = client.send(data[total : total + next_len])
            except Exception as e:
                self._log("send error", type(e).__name__, e, "total", total, "size", size)
                raise _SendTimeout("send error total={} size={}".format(total, size))
            if not sent:
                if _ticks_diff(deadline, _ticks_ms()) <= 0:
                    raise _SendTimeout("send timeout total={} size={}".format(total, size))
                _sleep_ms(10)
                continue
            total += sent
            self._log("send chunk", sent, "total", total, "size", size)
            _sleep_ms(SEND_YIELD_MS)
        if total < size:
            raise OSError("short send {}<{}".format(total, size))

    def _handle_request(self, client, method, target, body):
        path, query = _split_target(target)

        if path == "/health":
            self._send(client, 200, "application/json", '{"ok":true}')
            return

        if method == "GET" and path == "/diag":
            size = 0
            try:
                size = int(query.get("bytes", "0") or "0")
            except Exception:
                size = 0
            if size > 0:
                if size > 4096:
                    size = 4096
                self._send(client, 200, "text/plain; charset=utf-8", "D" * size)
                return
            html_size = 0
            try:
                html_size = int(query.get("html", "0") or "0")
            except Exception:
                html_size = 0
            if html_size > 0:
                if html_size > 4096:
                    html_size = 4096
                prefix = "<!doctype html><html><body><pre>"
                suffix = "</pre></body></html>"
                fill_len = max(0, html_size - len(prefix) - len(suffix))
                self._send(
                    client,
                    200,
                    "text/html; charset=utf-8",
                    prefix + ("H" * fill_len) + suffix,
                )
                return
            if query.get("formtext") == "1":
                self._send(
                    client,
                    200,
                    "text/plain; charset=utf-8",
                    render_minimal_form_html(_current_values()),
                )
                return
            self._send(
                client,
                200,
                "text/html; charset=utf-8",
                "<!doctype html><html><body>UHS diag OK</body></html>",
            )
            return

        if method == "GET" and path == "/favicon.ico":
            self._send(client, 404, body="")
            return

        if method == "GET" and path == "/":
            if not self._token_ok(query, {}):
                self._send(client, 403, body="Forbidden")
                return
            self._send(
                client,
                200,
                "text/html; charset=utf-8",
                render_minimal_form_html(_current_values()),
            )
            return

        if method == "POST" and path == "/save":
            form = parse_form_urlencoded(body)
            if not self._token_ok(query, form):
                self._send(client, 403, body="Forbidden")
                return
            updates = {}
            for key, _label, typ, _choices in _EDITABLE_FIELDS:
                if typ == "checkbox":
                    updates[key] = key in form and str(form.get(key, "")).lower() in ("1", "true", "on", "yes")
                elif key in form:
                    updates[key] = form.get(key)
            try:
                from storage import config_registry

                ok, errors = config_registry.save_updates(updates)
            except Exception as e:
                ok, errors = False, str(e)
            if not ok:
                self._send(
                    client,
                    400,
                    "text/html; charset=utf-8",
                    render_minimal_form_html(dict(_current_values(), **updates), error=errors),
                )
                return
            self._send(client, 200, "text/html; charset=utf-8", "Saved. Rebooting...")
            try:
                import machine

                time.sleep_ms(200)
                machine.reset()
            except Exception:
                pass
            return

        if method == "POST" and path == "/update":
            form = parse_form_urlencoded(body)
            if not self._token_ok(query, form):
                self._send(client, 403, body="Forbidden")
                return
            try:
                from storage import config_registry

                ok, error = config_registry.set_update_requested(True)
            except Exception as e:
                ok, error = False, str(e)
            if not ok:
                self._send(client, 500, "text/html; charset=utf-8", "Update request failed: {}".format(error))
                return
            self._send(client, 200, "text/html; charset=utf-8", "Update requested. Rebooting...")
            try:
                import machine

                time.sleep_ms(200)
                machine.reset()
            except Exception:
                pass
            return

        self._send(client, 404, body="Not found")

    def _token_ok(self, query, form):
        if not self._cfg.get("require_token"):
            return True
        return (query.get("k") or form.get("k") or "") == self._token
