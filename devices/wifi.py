"""
Wi-Fi device manager for UIFlow2 (non-blocking connect).
"""

import time

try:
    from memory_debug import snapshot as _debug_snapshot
except Exception:
    _debug_snapshot = None


def _mem_snapshot(tag, enabled=True):
    if enabled and _debug_snapshot:
        try:
            _debug_snapshot(tag, enabled=True, collect=False)
        except Exception:
            pass


def _wlan_state(wlan):
    if wlan is None:
        return "wlan=None"
    connected = "?"
    active = "?"
    status = "?"
    ip = ""
    try:
        connected = wlan.isconnected()
    except Exception:
        pass
    try:
        active = wlan.active()
    except Exception:
        pass
    try:
        value = wlan.status()
        if isinstance(value, int):
            status = "0x{:04x}".format(value)
        else:
            status = value
    except Exception:
        pass
    try:
        if connected:
            ip = " ip={}".format(wlan.ifconfig()[0])
    except Exception:
        pass
    return "connected={} active={} status={}{}".format(connected, active, status, ip)


class WifiDevice:
    def __init__(self, debug=False):
        self._debug = debug
        self._started = False
        self._connect_requested = False
        self._done = False
        self._failed = False
        self._wlan = None
        self._last_log_ms = 0

    def tick(self):
        if self._done or self._failed:
            return
        if not self._connect_requested:
            return
        if not self._started:
            self._start_connect()
            return
        if self._wlan is None:
            self._failed = True
            return
        if self._wlan.isconnected():
            self._done = True
            if self._debug:
                print("[WiFi] Connected:", self._wlan.ifconfig()[0])
            return
        if self._debug:
            now = time.ticks_ms()
            if time.ticks_diff(now, self._last_log_ms) > 3000:
                self._last_log_ms = now
                print("[WiFi] Connecting...")

    def ensure_connected(self, timeout_s=30):
        """
        Blocking connect: starts the connection if needed and waits until the
        interface is up or timeout_s seconds have elapsed.

        The interface is never cycled down so the UIFlow2 cloud WebSocket stays
        alive throughout.  Returns True if connected, False on timeout/error.
        """
        if self._done:
            _mem_snapshot("wifi.ensure.already_done", enabled=self._debug)
            return True
        self.request_connection()
        if not self._started:
            _mem_snapshot("wifi.ensure.before_start", enabled=self._debug)
            self._start_connect()
        if self._done:
            _mem_snapshot("wifi.ensure.after_start_done", enabled=self._debug)
            return True
        if self._failed or self._wlan is None:
            _mem_snapshot("wifi.ensure.failed", enabled=self._debug)
            if self._debug:
                print("[WiFi] ensure failed: {}".format(_wlan_state(self._wlan)))
            return False
        _mem_snapshot("wifi.ensure.wait_start", enabled=self._debug)
        if self._debug:
            print("[WiFi] ensure wait: {}".format(_wlan_state(self._wlan)))
        deadline = time.ticks_add(time.ticks_ms(), timeout_s * 1000)
        last_log_ms = 0
        while not self._wlan.isconnected():
            if self._debug:
                now = time.ticks_ms()
                if last_log_ms == 0 or time.ticks_diff(now, last_log_ms) > 3000:
                    last_log_ms = now
                    _mem_snapshot("wifi.ensure.waiting", enabled=True)
                    print("[WiFi] ensure waiting: {}".format(_wlan_state(self._wlan)))
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                if self._debug:
                    _mem_snapshot("wifi.ensure.timeout", enabled=True)
                    print("[WiFi] Timeout after {}s".format(timeout_s))
                    print("[WiFi] timeout state: {}".format(_wlan_state(self._wlan)))
                return False
            try:
                import M5
                M5.update()
            except Exception:
                pass
            time.sleep_ms(200)
        self._done = True
        # DNS/routing may not be ready immediately after DHCP; 500 ms is enough.
        time.sleep_ms(500)
        _mem_snapshot("wifi.ensure.connected", enabled=self._debug)
        if self._debug:
            print("[WiFi] Connected:", self._wlan.ifconfig()[0])
        return True

    def request_connection(self):
        """Enable background connection attempts without starting them twice."""
        if not self._done and not self._failed:
            self._connect_requested = True

    def _start_connect(self):
        self._connect_requested = True
        self._started = True
        _mem_snapshot("wifi.start.begin", enabled=self._debug)
        try:
            import network

            self._wlan = network.WLAN(network.STA_IF)
            if self._wlan.isconnected():
                self._done = True
                _mem_snapshot("wifi.start.already_connected", enabled=self._debug)
                if self._debug:
                    print("[WiFi] Already connected:", self._wlan.ifconfig()[0])
                return
            if not self._wlan.active():
                self._wlan.active(True)
            ssid, pswd, source = _load_wifi_credentials()
            if not ssid:
                raise RuntimeError("missing WiFi SSID")
            self._wlan.connect(ssid, pswd)
            _mem_snapshot("wifi.start.after_connect", enabled=self._debug)
            if self._debug:
                print("[WiFi] Background connect start ({}): {}".format(source, ssid))
                print("[WiFi] start state: {}".format(_wlan_state(self._wlan)))
        except Exception as e:
            self._failed = True
            _mem_snapshot("wifi.start.failed", enabled=self._debug)
            if self._debug:
                print("[WiFi] Background connect failed:", e)
                print("[WiFi] failed state: {}".format(_wlan_state(self._wlan)))


def _load_wifi_credentials():
    """
    Return (ssid, password, source) with priority:
    1) UIFlow NVS namespace "uiflow" keys "ssid0"/"pswd0"
    2) config.py keys WIFI_SSID / WIFI_PASSWORD (or WIFI_PSWD alias)
    """
    # 1) NVS credentials
    try:
        import esp32
        nvs = esp32.NVS("uiflow")
        ssid = nvs.get_str("ssid0")
        pswd = nvs.get_str("pswd0")
        if ssid:
            return ssid, pswd or "", "nvs"
    except Exception:
        pass

    # 2) config.py fallback
    try:
        import config
        ssid = getattr(config, "WIFI_SSID", "") or ""
        pswd = (
            getattr(config, "WIFI_PASSWORD", "")
            or getattr(config, "WIFI_PSWD", "")
            or ""
        )
        if ssid:
            return ssid, pswd, "config"
    except Exception:
        pass

    return "", "", "none"
