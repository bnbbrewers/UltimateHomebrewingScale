"""
Brewing Software API Interface
For UIFlow2.0 / MicroPython on M5Stack
"""

import gc
import time

try:
    import config as _config
    _DEBUG = getattr(_config, 'DEBUG', False)
except Exception:
    _DEBUG = False


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


class ApiBase:
    """Abstract base class for brewing software API implementations."""

    def _get(self, url, headers, retries=2):
        """
        HTTP GET helper shared by all implementations.

        Ensures WiFi is connected, then performs the request with up to
        `retries` attempts.  The first attempt may fail with -202
        (ESP_ERR_HTTP_CONNECT) if the network stack isn't fully ready yet;
        a 1 s pause between retries is enough for DNS/routing to stabilise.
        """
        from core.hardware_manager import HardwareManager
        if not HardwareManager.get_instance().wifi.ensure_connected():
            raise OSError("WiFi not connected")

        last_exc = None
        for attempt in range(max(1, retries)):
            try:
                import requests
                resp = requests.get(url, headers=headers)
                return resp
            except Exception as e:
                last_exc = e
                if _DEBUG:
                    print(f"[HTTP] attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep_ms(1000)
                    gc.collect()
        raise last_exc

    def warmup(self):
        """Pre-establish TLS connection while the C-heap is clean."""
        pass

    def release_session(self):
        """Close network session to free C-heap. Reconnects lazily on next call."""
        pass

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


# Backward compatibility with existing modules.
BrewingSoftwareAPI = ApiBase
