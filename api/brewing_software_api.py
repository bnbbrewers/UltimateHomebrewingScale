"""
Brewing Software API Interface
For UIFlow2.0 / MicroPython on M5Stack
"""

import gc
import time

from network import http_transport

try:
    import config as _config
    _DEBUG = getattr(_config, 'DEBUG', False)
except Exception:
    _DEBUG = False


class Batch:
    """Represents a brewing batch"""
    def __init__(self, batch_id, name, recipe_id=""):
        self.batch_id = batch_id
        self.name = name
        self.recipe_id = recipe_id
    
    def __repr__(self):
        return (
            f"Batch(batch_id='{self.batch_id}', "
            f"name='{self.name}', recipe_id='{self.recipe_id}')"
        )


class Malt:
    """Represents a malt/grain ingredient"""
    def __init__(self, name, ebc, amount):
        self.name = name
        self.ebc = ebc
        self.amount = amount  # in kg or lbs depending on settings
    
    def __repr__(self):
        return f"Malt(name='{self.name}', ebc={self.ebc}, amount={self.amount})"


class HopStep:
    """Represents a single hop addition step"""
    def __init__(self, step_name, step_amount):
        self.step_name = step_name
        self.step_amount = step_amount  # in grams

    def __repr__(self):
        return f"HopStep(step_name='{self.step_name}', step_amount={self.step_amount})"


class Hop:
    """Represents a hop grouped with all its addition steps"""
    def __init__(self, hop_name, steps=None):
        self.hop_name = hop_name
        self.steps = steps or []

    def __repr__(self):
        return f"Hop(hop_name='{self.hop_name}', steps={self.steps})"


class ApiBase:
    """Abstract base class for brewing software API implementations."""

    def __init__(self, wifi_device=None):
        self._wifi_device = wifi_device

    def _get(self, url, headers, retries=2, stream=False):
        """
        HTTP GET helper shared by all implementations.

        Ensures WiFi is connected, then performs the request with up to
        `retries` attempts.  The first attempt may fail with -202
        (ESP_ERR_HTTP_CONNECT) if the network stack isn't fully ready yet;
        a 1 s pause between retries is enough for DNS/routing to stabilise.
        """
        wifi_device = self._wifi_device
        if wifi_device is None:
            # Compatibility for direct connector construction by older apps.
            from core.hardware_manager import HardwareManager
            wifi_device = HardwareManager.get_instance().wifi
        if not wifi_device.ensure_connected():
            raise OSError("WiFi not connected")

        last_exc = None
        for attempt in range(max(1, retries)):
            try:
                requests_module = http_transport.default_requests_module()
                if requests_module is None:
                    raise RuntimeError("Missing requests2 module")
                return http_transport.get(
                    requests_module,
                    url,
                    headers=headers,
                    stream=stream,
                )
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
        Retrieve hops for a specific batch, grouped by hop name.

        Args:
            batch_id: The unique identifier of the batch

        Returns:
            List[Hop]: Each entry has .hop_name and .steps,
            a list of HopStep(step_name, step_amount).
        """
        raise NotImplementedError("Subclass must implement get_hops()")

    def get_hops_list(self, batch_id):
        """
        Compact hop format for memory-constrained UIs.

        Returns:
            List[dict]: [{"name": str, "steps": [(step_name, step_amount), ...]}, ...]
        """
        hops_list = []
        hops = self.get_hops(batch_id)
        for hop in hops:
            steps = []
            for step in hop.steps:
                steps.append((step.step_name, step.step_amount))
            if steps:
                hops_list.append({"name": hop.hop_name, "steps": steps})
        return hops_list


# Backward compatibility with existing modules.
BrewingSoftwareAPI = ApiBase
