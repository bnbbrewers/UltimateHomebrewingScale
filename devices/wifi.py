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
