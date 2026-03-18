"""
Wi-Fi device manager for UIFlow2 (non-blocking connect).
"""

import time


class WifiDevice:
    def __init__(self, debug=False):
        self._debug = debug
        self._started = False
        self._done = False
        self._failed = False
        self._wlan = None
        self._last_log_ms = 0

    def tick(self):
        if self._done or self._failed:
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
            return True
        if not self._started:
            self._start_connect()
        if self._done:
            return True
        if self._failed or self._wlan is None:
            return False
        deadline = time.ticks_add(time.ticks_ms(), timeout_s * 1000)
        while not self._wlan.isconnected():
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                if self._debug:
                    print("[WiFi] Timeout after {}s".format(timeout_s))
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
        if self._debug:
            print("[WiFi] Connected:", self._wlan.ifconfig()[0])
        return True

    def _start_connect(self):
        self._started = True
        try:
            import network
            import esp32

            self._wlan = network.WLAN(network.STA_IF)
            if self._wlan.isconnected():
                self._done = True
                if self._debug:
                    print("[WiFi] Already connected:", self._wlan.ifconfig()[0])
                return
            if not self._wlan.active():
                self._wlan.active(True)
            nvs = esp32.NVS("uiflow")
            ssid = nvs.get_str("ssid0")
            pswd = nvs.get_str("pswd0")
            self._wlan.connect(ssid, pswd)
            if self._debug:
                print("[WiFi] Background connect start:", ssid)
        except Exception as e:
            self._failed = True
            if self._debug:
                print("[WiFi] Background connect failed:", e)
