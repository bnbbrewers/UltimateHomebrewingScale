"""
Brewfather API Implementation
For UIFlow2.0 / MicroPython on M5Stack
"""

import gc
import binascii
import json
import os
from .brewing_software_api import ApiBase, Batch, Malt, Hop, HopStep
from memory_debug import snapshot as mem_snapshot

try:
    import config as _config
    _DEBUG = getattr(_config, "DEBUG", False)
except Exception:
    _DEBUG = False


class BrewfatherAPI(ApiBase):
    """Implementation of BrewingSoftwareAPI for Brewfather"""

    _HOST = "api.brewfather.app"
    _BASE_PATH = "/v2"
    _TMP_JSON_PATH = "brewfather_api.tmp"

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

    # ── stateless HTTP helpers ─────────────────────────────────────

    @staticmethod
    def _remove_file(path):
        try:
            os.remove(path)
        except Exception:
            pass

    def _spool_response_to_file(self, resp, path):
        # On the M5Dial, parsing JSON while the HTTPS response is still open
        # can exhaust ESP-IDF's largest contiguous heap block. Spool the body
        # in small chunks so TLS/socket buffers can be released before parsing.
        mem_snapshot("api.spool.start", enabled=_DEBUG, collect=False)
        mode = "content"
        with open(path, "wb") as f:
            raw = getattr(resp, "raw", None)
            if raw is not None and hasattr(raw, "read"):
                mode = "raw"
                total = 0
                chunks = 0
                mem_snapshot("api.spool.raw.start", enabled=_DEBUG, collect=False)
                while True:
                    try:
                        chunk = raw.read(512)
                    except Exception as e:
                        if _DEBUG:
                            print("[API] raw.read error chunks={} bytes={}: {}".format(
                                chunks, total, e))
                        mem_snapshot("api.spool.raw.error", enabled=_DEBUG, collect=False)
                        raise
                    if chunks == 0:
                        mem_snapshot("api.spool.raw.after_first_read", enabled=_DEBUG, collect=False)
                    if not chunk:
                        break
                    f.write(chunk)
                    total += len(chunk)
                    chunks += 1
                    del chunk
                if _DEBUG:
                    print("[API] raw.done chunks={} bytes={}".format(chunks, total))
                mem_snapshot("api.spool.raw.done", enabled=_DEBUG, collect=False)
                return mode

            iter_content = getattr(resp, "iter_content", None)
            if iter_content:
                mode = "iter"
                total = 0
                chunks = 0
                mem_snapshot("api.spool.iter.start", enabled=_DEBUG, collect=False)
                try:
                    for chunk in iter_content(512):
                        if chunks == 0:
                            mem_snapshot("api.spool.iter.after_first_read", enabled=_DEBUG, collect=False)
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
                            chunks += 1
                        del chunk
                except Exception as e:
                    if _DEBUG:
                        print("[API] iter_content error chunks={} bytes={}: {}".format(
                            chunks, total, e))
                    mem_snapshot("api.spool.iter.error", enabled=_DEBUG, collect=False)
                    raise
                if _DEBUG:
                    print("[API] iter.done chunks={} bytes={}".format(chunks, total))
                mem_snapshot("api.spool.iter.done", enabled=_DEBUG, collect=False)
                return mode

            # Last-resort fallback for request implementations without a raw
            # stream. This may allocate the full body while TLS buffers remain.
            mem_snapshot("api.spool.content.before", enabled=_DEBUG, collect=False)
            content = getattr(resp, "content", b"")
            mem_snapshot("api.spool.content.after_get", enabled=_DEBUG, collect=False)
            f.write(content)
            del content
            mem_snapshot("api.spool.content.done", enabled=_DEBUG, collect=False)
        return mode

    @staticmethod
    def _load_json_file(path):
        with open(path, "r") as f:
            load = getattr(json, "load", None)
            if load:
                return load(f)
            return json.loads(f.read())

    def _get_json(self, path):
        """GET returning (status_code, parsed_json|None) using plain requests."""
        url = "https://{}{}".format(self._HOST, path)
        if _DEBUG:
            print("[API] GET {}".format(path))
        mem_snapshot("api.http.pre", enabled=_DEBUG, collect=True)
        resp = None
        self._remove_file(self._TMP_JSON_PATH)
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
                    hasattr(resp, "content"),
                ))
            spool_mode = self._spool_response_to_file(resp, self._TMP_JSON_PATH)
            if _DEBUG:
                print("[API] body_spooled mode={}".format(spool_mode))
            mem_snapshot("api.body.spooled", enabled=_DEBUG, collect=False)
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass
                resp = None
            gc.collect()
            mem_snapshot("api.body.closed", enabled=_DEBUG, collect=False)
            # Parse only after closing the response. This avoids holding
            # requests2/TLS buffers and the decoded JSON tree at the same time.
            data = self._load_json_file(self._TMP_JSON_PATH)
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
                try:
                    resp.close()
                except Exception:
                    pass
            self._remove_file(self._TMP_JSON_PATH)

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
            hops_list = self.get_hops_list(batch_id)
            hops = []
            for hop in hops_list:
                hop_obj = Hop(hop_name=hop["name"])
                for step_name, step_amount in hop["steps"]:
                    hop_obj.steps.append(HopStep(step_name=step_name, step_amount=step_amount))
                hops.append(hop_obj)
            return hops
        except Exception as e:
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
            print("Error: {}".format(e))
            return []
        mem_snapshot("api.hops.compact", enabled=_DEBUG, collect=False)
        return hops_list
