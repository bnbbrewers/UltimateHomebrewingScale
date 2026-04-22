"""Lightweight embedded setup portal (memory-focused)."""

import socket
import time

from . import config_store
from .config_keys import EDITABLE_KEYS, EDITABLE_ORDER

PORTAL_HTTP_HOST = "0.0.0.0"
PORTAL_HTTP_PORT = 8080


def _load_setup_cfg():
    try:
        import config
    except Exception:
        config = None

    def _get(name, default):
        if config is None:
            return default
        return getattr(config, name, default)

    return {
        "ap_ssid": _get("SETUP_AP_SSID", "UHB-Scale-Setup"),
        "ap_password": _get("SETUP_AP_PASSWORD", "brewsetup123"),
        "require_token": bool(_get("SETUP_REQUIRE_TOKEN", False)),
        "token": str(_get("SETUP_TOKEN", "") or ""),
        "reboot_after_save": bool(_get("SETUP_REBOOT_AFTER_SAVE", False)),
    }


def build_portal_url(sta_ip=None, ap_ip=None, port=PORTAL_HTTP_PORT, token=""):
    ip = sta_ip or ap_ip or "192.168.4.1"
    url = "http://{}:{}/".format(ip, int(port))
    if token:
        url += "?k={}".format(token)
    return url


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


def render_form_html(values, saved=False, errors=None, token="", mode="sta", ssid=""):
    errors = errors or {}
    p = []
    p.append("<!doctype html><html><head><meta charset='utf-8'>")
    p.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    p.append("<title>Scale setup</title></head><body>")
    p.append("<h3>Scale setup</h3>")
    if mode == "ap":
        p.append("<p>AP: <b>{}</b></p>".format(_html_escape(ssid)))
    if saved:
        p.append("<p><b>Saved</b></p>")
    if errors:
        p.append("<p><b>Invalid fields</b></p>")
    p.append("<form method='post' action='/save'>")
    if token:
        p.append("<input type='hidden' name='k' value='{}'>".format(_html_escape(token)))

    for key in EDITABLE_ORDER:
        spec = EDITABLE_KEYS[key]
        val = values.get(key, spec.get("default"))
        p.append("<p>{}<br>".format(_html_escape(spec.get("label") or key)))
        typ = spec.get("type")
        if typ == "bool":
            checked = " checked" if bool(val) else ""
            p.append("<input type='checkbox' name='{}' value='on'{}>".format(key, checked))
        elif typ == "enum":
            p.append("<select name='{}'>".format(key))
            for choice in spec.get("choices", []):
                sel = " selected" if str(val) == str(choice) else ""
                p.append("<option value='{0}'{1}>{0}</option>".format(_html_escape(choice), sel))
            p.append("</select>")
        elif typ == "int":
            p.append(
                "<input type='number' name='{0}' value='{1}' min='{2}' max='{3}'>".format(
                    key,
                    _html_escape(val),
                    _html_escape(spec.get("min", "")),
                    _html_escape(spec.get("max", "")),
                )
            )
        else:
            input_type = "password" if "PASSWORD" in key or "API_KEY" in key else "text"
            p.append("<input type='{0}' name='{1}' value='{2}'>".format(input_type, key, _html_escape(val)))
        if key in errors:
            p.append("<br><small>{}</small>".format(_html_escape(errors[key])))
        p.append("</p>")

    p.append("<p><button type='submit'>Save</button></p></form>")
    p.append("<form method='post' action='/reboot'>")
    if token:
        p.append("<input type='hidden' name='k' value='{}'>".format(_html_escape(token)))
    p.append("<p><button type='submit'>Reboot</button></p></form>")
    p.append("</body></html>")
    return "".join(p)


class SetupPortalService:
    def __init__(self, wifi_device=None, debug=False):
        self._wifi = wifi_device
        self._debug = bool(debug)
        self._cfg = _load_setup_cfg()
        self._listener = None
        self._mode = "none"
        self._sta_ip = ""
        self._ap_ip = ""
        self._url = ""
        self._ap = None

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
        if self._listener:
            try:
                self._listener.close()
            except Exception:
                pass
        self._listener = None
        if self._ap:
            try:
                self._ap.active(False)
            except Exception:
                pass

    def tick(self):
        if not self._listener:
            return
        try:
            client, addr = self._listener.accept()
        except Exception:
            return
        self._log("accept", addr)
        try:
            self._handle_client(client)
        except Exception as e:
            self._log("client error:", e)
            try:
                self._send(client, 500, "text/plain; charset=utf-8", "Internal error")
            except Exception:
                pass
        try:
            client.close()
        except Exception:
            pass

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
            try:
                return ap.ifconfig()[0]
            except Exception:
                return "192.168.4.1"
        except Exception:
            return "192.168.4.1"

    def _start_server_if_needed(self):
        if self._listener:
            return
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
        while b"\r\n\r\n" not in data and len(data) < 4096:
            try:
                chunk = client.recv(1024)
            except Exception:
                break
            if not chunk:
                break
            data += chunk
        head, sep, tail = data.partition(b"\r\n\r\n")
        if not sep:
            return "", "", {}, ""
        try:
            head_text = head.decode("utf-8")
        except Exception:
            head_text = head.decode("latin-1")

        lines = head_text.split("\r\n")
        parts = (lines[0] if lines else "").split(" ")
        method = parts[0] if len(parts) > 0 else ""
        target = parts[1] if len(parts) > 1 else "/"
        self._log("request", method, target)
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        body = tail
        content_length = 0
        try:
            content_length = int(headers.get("content-length", "0") or "0")
        except Exception:
            content_length = 0
        while len(body) < content_length and len(body) < 4096:
            try:
                chunk = client.recv(min(512, content_length - len(body)))
            except Exception:
                break
            if not chunk:
                break
            body += chunk
        try:
            body_text = body.decode("utf-8")
        except Exception:
            body_text = body.decode("latin-1")
        return method, target, headers, body_text

    @staticmethod
    def _split_target(target):
        if "?" in target:
            path, query = target.split("?", 1)
        else:
            path, query = target, ""
        return path, parse_form_urlencoded(query)

    def _token_ok(self, query, form):
        if not self._cfg.get("require_token"):
            return True
        return (query.get("k") or form.get("k") or "") == self._token

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
        self._log("response", status_code, "bytes", len(payload))
        self._send_all(client, head)
        self._send_all(client, payload)

    def _send_all(self, client, data):
        if not data:
            return
        try:
            client.sendall(data)
            return
        except Exception:
            pass
        total = 0
        deadline = time.ticks_add(time.ticks_ms(), 3000)
        size = len(data)
        while total < size:
            sent = 0
            try:
                sent = client.send(data[total : total + 512])
            except Exception:
                sent = 0
            if not sent:
                if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                    raise OSError("send timeout")
                time.sleep_ms(10)
                continue
            total += sent
        if total < size:
            raise OSError("short send {}<{}".format(total, size))

    def _handle_client(self, client):
        method, target, _headers, body = self._read_request(client)
        if not method:
            self._log("empty request")
            self._send(client, 400, "text/plain; charset=utf-8", "Bad request")
            return
        path, query = self._split_target(target)

        if path == "/health":
            self._send(client, 200, "application/json", '{"ok":true}')
            return

        if method == "GET" and path == "/":
            if not self._token_ok(query, {}):
                self._send(client, 403, body="Forbidden")
                return
            values = config_store.load_current_values()
            html = render_form_html(
                values,
                saved=(query.get("saved") == "1"),
                errors=None,
                token=self._token if self._cfg.get("require_token") else "",
                mode=self._mode,
                ssid=self._cfg.get("ap_ssid", ""),
            )
            self._send(client, 200, "text/html; charset=utf-8", html)
            return

        if method == "POST" and path == "/save":
            form = parse_form_urlencoded(body)
            if not self._token_ok(query, form):
                self._send(client, 403, body="Forbidden")
                return

            updates = {}
            for key in EDITABLE_ORDER:
                spec = EDITABLE_KEYS[key]
                if spec.get("type") == "bool":
                    updates[key] = key in form and str(form.get(key, "")).lower() in ("1", "true", "on", "yes")
                elif key in form:
                    updates[key] = form.get(key)

            ok, errors = config_store.save_updates(updates)
            if ok:
                if self._cfg.get("reboot_after_save"):
                    self._send(client, 200, "text/html; charset=utf-8", "Saved. Rebooting...")
                    try:
                        import machine

                        time.sleep_ms(200)
                        machine.reset()
                    except Exception:
                        pass
                    return
                loc = "/?saved=1"
                if self._cfg.get("require_token"):
                    loc += "&k={}".format(self._token)
                self._send(client, 303, headers={"Location": loc})
                return

            values = config_store.load_current_values()
            for k, v in updates.items():
                values[k] = v
            html = render_form_html(
                values,
                saved=False,
                errors=errors,
                token=self._token if self._cfg.get("require_token") else "",
                mode=self._mode,
                ssid=self._cfg.get("ap_ssid", ""),
            )
            self._send(client, 400, "text/html; charset=utf-8", html)
            return

        if method == "POST" and path == "/reboot":
            form = parse_form_urlencoded(body)
            if not self._token_ok(query, form):
                self._send(client, 403, body="Forbidden")
                return
            self._send(client, 200, "text/html; charset=utf-8", "Rebooting...")
            try:
                import machine

                time.sleep_ms(200)
                machine.reset()
            except Exception:
                pass
            return

        self._send(client, 404, body="Not found")
