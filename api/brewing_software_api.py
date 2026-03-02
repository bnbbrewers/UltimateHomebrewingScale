"""
Brewing Software API Interface
For UIFlow2.0 / MicroPython on M5Stack
"""

import gc
import time
import requests

try:
    import config as _config
    _DEBUG = getattr(_config, 'DEBUG', False)
except Exception:
    _DEBUG = False


def _ensure_wifi(timeout_s=30):
    """
    Connect to WiFi using UIFlow2 NVS credentials (ssid0 / pswd0) and wait
    until the interface is up.  Called from _get() so WiFi connects only when
    the first API request is made – after the loading screen is already shown.

    The interface is never cycled down so the UIFlow2 cloud WebSocket stays
    alive throughout.

    Returns True if connected within timeout_s seconds, False otherwise.
    """
    try:
        import network, esp32
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            return True
        if not wlan.active():
            wlan.active(True)
        nvs  = esp32.NVS("uiflow")
        ssid = nvs.get_str("ssid0")
        pswd = nvs.get_str("pswd0")
        if _DEBUG:
            print("[WiFi] Connecting to:", ssid)
        wlan.connect(ssid, pswd)
        deadline = time.ticks_add(time.ticks_ms(), timeout_s * 1000)
        while not wlan.isconnected():
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                if _DEBUG:
                    print("[WiFi] Timeout after {}s".format(timeout_s))
                return False
            try:
                import M5
                M5.update()
            except Exception:
                pass
            time.sleep_ms(200)
        # wlan.isconnected() is True once DHCP assigns an IP, but DNS and
        # routing may not be ready yet – 500 ms is enough to stabilise.
        time.sleep_ms(500)
        if _DEBUG:
            print("[WiFi] Connected:", wlan.ifconfig()[0])
        return True
    except Exception as e:
        if _DEBUG:
            print("[WiFi] Error:", e)
        return False


class Batch:
    """Represents a brewing batch"""
    def __init__(self, batch_id, name):
        self.batch_id = batch_id
        self.name = name
    
    def __repr__(self):
        return f"Batch(batch_id='{self.batch_id}', name='{self.name}')"


class Malt:
    """Represents a malt/grain ingredient"""
    def __init__(self, name, ebc, amount):
        self.name = name
        self.ebc = ebc
        self.amount = amount  # in kg or lbs depending on settings
    
    def __repr__(self):
        return f"Malt(name='{self.name}', ebc={self.ebc}, amount={self.amount})"


class Hop:
    """Represents a hop ingredient"""
    def __init__(self, name, amount, use, time):
        self.name = name
        self.amount = amount  # in grams
        self.use = use  # Boil, Whirlpool, Dry Hop, etc.
        self.time = time  # in minutes
    
    def __repr__(self):
        return f"Hop(name='{self.name}', amount={self.amount}, use='{self.use}', time={self.time})"


class BrewingSoftwareAPI:
    """Base class for brewing software API implementations"""

    def _get(self, url, headers, retries=2):
        """
        HTTP GET helper shared by all implementations.

        Ensures WiFi is connected, then performs the request with up to
        `retries` attempts.  The first attempt may fail with -202
        (ESP_ERR_HTTP_CONNECT) if the network stack isn't fully ready yet;
        a 1 s pause between retries is enough for DNS/routing to stabilise.
        """
        if not _ensure_wifi():
            raise OSError("WiFi not connected")

        gc.collect()
        if _DEBUG:
            free  = gc.mem_free()
            alloc = gc.mem_alloc()
            print(f"[MEM] before request  free={free}  alloc={alloc}  total={free+alloc}")
            try:
                import micropython
                micropython.mem_info()
            except Exception:
                pass

        last_exc = None
        for attempt in range(max(1, retries)):
            try:
                return requests.get(url, headers=headers)
            except Exception as e:
                last_exc = e
                if _DEBUG:
                    print(f"[HTTP] attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep_ms(1000)
                    gc.collect()
        raise last_exc

    def get_batches(self):
        """
        Retrieve all batches from the brewing software
        
        Returns:
            List[Batch]: List of batches with batch_id and name
        """
        raise NotImplementedError("Subclass must implement get_batches()")
    
    def get_malts(self, batch_id):
        """
        Retrieve malts/grains for a specific batch
        
        Args:
            batch_id: The unique identifier of the batch
            
        Returns:
            List[Malt]: List of malts with name, EBC and amount
        """
        raise NotImplementedError("Subclass must implement get_malts()")
    
    def get_hops(self, batch_id):
        """
        Retrieve hops for a specific batch
        
        Args:
            batch_id: The unique identifier of the batch
            
        Returns:
            List[Hop]: List of hops with name, amount, use and time
        """
        raise NotImplementedError("Subclass must implement get_hops()")
