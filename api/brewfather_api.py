"""
Brewfather API Implementation
For UIFlow2.0 / MicroPython on M5Stack
"""

import gc
import binascii
from .brewing_software_api import ApiBase, Batch, Malt, Hop, HopStep
from netcore import http_transport

try:
    import config as _config
    _DEBUG = getattr(_config, "DEBUG", False)
except Exception:
    _DEBUG = False

if _DEBUG:
    from memory_debug import snapshot as mem_snapshot
else:
    def mem_snapshot(*args, **kwargs):
        return None


class BrewfatherAPI(ApiBase):
    """Implementation of BrewingSoftwareAPI for Brewfather"""

    _HOST = "api.brewfather.app"
    _BASE_PATH = "/v2"
    _TMP_JSON_PATH = "brewfather_api.tmp"

    def __init__(self, wifi_device=None):
        super().__init__(wifi_device=wifi_device)
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
        }

    # ── stateless HTTP helpers ─────────────────────────────────────

    def _get_json(self, path):
        """GET returning (status_code, parsed_json|None) using plain requests."""
        self._last_error = None
        url = "https://{}{}".format(self._HOST, path)
        if _DEBUG:
            print("[API] GET {}".format(path))
        gc.collect()
        mem_snapshot("api.http.pre", enabled=_DEBUG, collect=True)
        resp = None
        http_transport.remove_file(self._TMP_JSON_PATH)
        try:
            resp = self._get(url, headers=self._headers, stream=True)
            status = getattr(resp, "status_code", None)
            if status is None:
                status = getattr(resp, "status", -1)

            mem_snapshot("api.http.post", enabled=_DEBUG, collect=False)
            if status != 200:
                if _DEBUG:
                    print("[API] HTTP {}".format(status))
                return status, None

            if _DEBUG:
                raw = getattr(resp, "raw", None)
                print("[API] stream raw={} iter={} content={}".format(
                    bool(raw is not None and hasattr(raw, "read")),
                    bool(getattr(resp, "iter_content", None)),
                    "not_checked",
                ))
            spool_mode = http_transport.spool_response_to_file(
                resp, self._TMP_JSON_PATH, max_content_bytes=65536
            )
            if _DEBUG:
                print("[API] body_spooled mode={}".format(spool_mode))
            mem_snapshot("api.body.spooled", enabled=_DEBUG, collect=False)
            if resp is not None:
                http_transport.close_response(resp)
                resp = None
            gc.collect()
            mem_snapshot("api.body.closed", enabled=_DEBUG, collect=False)
            # Parse only after closing the response. This avoids holding
            # requests2/TLS buffers and the decoded JSON tree at the same time.
            data = http_transport.load_json_file(self._TMP_JSON_PATH)
            if _DEBUG:
                try:
                    if isinstance(data, list):
                        print("[API] json_type=list len={}".format(len(data)))
                    elif isinstance(data, dict):
                        print("[API] json_type=dict keys={}".format(len(data)))
                    else:
                        print("[API] json_type={}".format(type(data)))
                except Exception:
                    pass
            gc.collect()
            mem_snapshot("api.json.parsed", enabled=_DEBUG, collect=False)
            return status, data
        finally:
            if resp is not None:
                http_transport.close_response(resp)
            http_transport.remove_file(self._TMP_JSON_PATH)

    # ── public API ─────────────────────────────────────────────────

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
            try:
                del batch_data
                del recipe
            except Exception:
                pass
            del data
            gc.collect()
            return batches

        except Exception as e:
            self._last_error = e
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
            try:
                del f
                del fermentables
            except Exception:
                pass
            del data
            gc.collect()
            return malts

        except Exception as e:
            self._last_error = e
            print("Error: {}".format(e))
            return []

    def get_hops(self, batch_id):
        try:
            hops_list = self.get_hops_list(batch_id)
            hops = []
            for hop in hops_list:
                hop_obj = Hop(hop_name=hop["name"])
                for step_name, step_amount in hop["steps"]:
                    hop_obj.steps.append(HopStep(step_name=step_name, step_amount=step_amount))
                hops.append(hop_obj)
            return hops
        except Exception as e:
            self._last_error = e
            print("Error: {}".format(e))
            return []

    @staticmethod
    def _group_hops(hops_data):
        groups = {}
        order = []
        for h in hops_data:
            name = h.get('name', 'Unknown Hop')
            use = h.get('use', '')
            t = h.get('time', 0)
            amount = h.get('amount', 0.0)
            unit = "d" if h.get('timeUnit') == "days" else "min"
            if name not in groups:
                groups[name] = []
                order.append(name)
            groups[name].append(("{} - {}{}".format(use, t, unit), amount))
        hops_list = []
        for name in order:
            hops_list.append({"name": name, "steps": groups[name]})
        return hops_list

    def get_hops_list(self, batch_id):
        try:
            status, data = self._get_json(
                "{}/batches/{}?include=recipe.hops".format(
                    self._BASE_PATH, batch_id
                )
            )
            if data is None:
                return []
            hops_list = self._group_hops(data.get("recipe", {}).get("hops", []))
            del data
            gc.collect()
            if _DEBUG:
                print("[API] hops_source=batch")
        except Exception as e:
            self._last_error = e
            print("Error: {}".format(e))
            return []
        mem_snapshot("api.hops.compact", enabled=_DEBUG, collect=False)
        return hops_list
