"""
Brewfather API Implementation
For UIFlow2.0 / MicroPython on M5Stack
"""

import gc
import json
import binascii
from .brewing_software_api import ApiBase, Batch, Malt, Hop, HopStep
from .tls_session import TlsSession

try:
    import config as _config
    _DEBUG = getattr(_config, "DEBUG", False)
except Exception:
    _DEBUG = False


class BrewfatherAPI(ApiBase):
    """Implementation of BrewingSoftwareAPI for Brewfather"""

    _HOST = "api.brewfather.app"
    _BASE_PATH = "/v2"

    def __init__(self):
        try:
            import config
            user_id = getattr(config, 'BREWFATHER_USER_ID', '')
            api_key  = getattr(config, 'BREWFATHER_API_KEY',  '')
        except ImportError:
            user_id = ''
            api_key  = ''

        self.user_id = user_id
        self.api_key  = api_key
        credentials = "{}:{}".format(user_id, api_key)
        b64 = binascii.b2a_base64(credentials.encode()).decode().strip()
        self._headers = {
            'Authorization': 'Basic {}'.format(b64),
            'Content-Type': 'application/json',
        }
        self._session = None

    # ── persistent-session helpers ─────────────────────────────────

    def _ensure_wifi(self):
        from core.hardware_manager import HardwareManager
        if not HardwareManager.get_instance().wifi.ensure_connected():
            raise OSError("WiFi not connected")

    def _get_json(self, path):
        """GET returning (status_code, parsed_json|None) over the kept-alive TLS socket."""
        self._ensure_wifi()
        if self._session is None:
            self._session = TlsSession(self._HOST)
        status, body = self._session.get(path, headers=self._headers)
        if status != 200 or not body:
            if _DEBUG:
                print("[API] HTTP {}".format(status))
            return status, None
        data = json.loads(body)
        del body
        gc.collect()
        return status, data

    # ── public API ─────────────────────────────────────────────────

    def warmup(self):
        """Establish the TLS connection while the IDF heap is still clean."""
        self._ensure_wifi()
        if self._session is None:
            self._session = TlsSession(self._HOST)
        if not self._session.is_connected:
            self._session.connect()

    def release_session(self):
        """Close the TLS socket to free ~32 KB of IDF C-heap (SSL buffers)."""
        if self._session is not None:
            self._session.close()

    def get_batches(self):
        try:
            status, data = self._get_json(
                "{}/batches?status=Brewing&include=_id".format(self._BASE_PATH)
            )
            if data is None:
                return []

            batches = []
            for batch_data in data:
                recipe = batch_data.get('recipe', {})
                batches.append(Batch(
                    batch_id=batch_data.get('_id', ''),
                    name=recipe.get('name', 'Unknown Recipe'),
                ))
            return batches

        except Exception as e:
            print("Error: {}".format(e))
            return []

    def get_malts(self, batch_id):
        try:
            status, data = self._get_json(
                "{}/batches/{}?include=recipe.fermentables".format(
                    self._BASE_PATH, batch_id
                )
            )
            if data is None:
                return []

            fermentables = data.get('recipe', {}).get('fermentables', [])
            malts = []
            for f in fermentables:
                if f.get('type') in ['Grain', 'Malt']:
                    malts.append(Malt(
                        name=f.get('name', 'Unknown Malt'),
                        ebc=f.get('color', 0.0),
                        amount=f.get('amount', 0.0),
                    ))
            return malts

        except Exception as e:
            print("Error: {}".format(e))
            return []

    def get_hops(self, batch_id):
        try:
            status, data = self._get_json(
                "{}/batches/{}?include=recipe.hops".format(
                    self._BASE_PATH, batch_id
                )
            )
            if data is None:
                return []

            hops_data = data.get('recipe', {}).get('hops', [])
            groups = {}
            order = []
            for h in hops_data:
                name = h.get('name', 'Unknown Hop')
                use = h.get('use', '')
                t = h.get('time', 0)
                amount = h.get('amount', 0.0)
                unit = "d" if h.get('timeUnit') == "days" else "min"
                step = HopStep(
                    step_name="{} - {}{}".format(use, t, unit),
                    step_amount=amount,
                )
                if name not in groups:
                    groups[name] = Hop(hop_name=name)
                    order.append(name)
                groups[name].steps.append(step)
            return [groups[n] for n in order]

        except Exception as e:
            print("Error: {}".format(e))
            return []
