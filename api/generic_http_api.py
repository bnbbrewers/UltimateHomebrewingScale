"""Provider-neutral SCALE_API v1 connector; no UI or actuator dependencies."""
import math
from .brewing_software_api import ApiBase, Batch, Malt
from netcore import http_transport
import runtime_debug


class IntegrationError(Exception):
    def __init__(self, status, code):
        self.status = status
        self.code = code
        super().__init__("HTTP {}: {}".format(status, code))


def valid_id(value):
    return (isinstance(value, str) and 0 < len(value) <= 100
            and all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in value))


def mass(row):
    # Unknown units stay unknown even if a server supplied a mass accidentally.
    value = row.get("targetWeightG")
    if row.get("unit") not in ("g", "kg") or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        return None
    return value


class GenericHttpAPI(ApiBase):
    def __init__(self, wifi_device=None):
        super().__init__(wifi_device)
        self.base_url = runtime_debug.setting("HTTP_API_BASE_URL", "").rstrip("/")
        self._tmp_path = "generic_api-{}.tmp".format(id(self))
        self.token = runtime_debug.setting("HTTP_API_TOKEN", "")

    def _json(self, path):
        if not self.base_url.startswith(("http://", "https://")):
            raise IntegrationError(0, "Configure HTTP API base URL")
        response = None
        tmp = self._tmp_path
        try:
            response = self._get(self.base_url + path,
                                 {"Authorization": "Bearer " + self.token}, retries=1, stream=True)
            status = getattr(response, "status_code", getattr(response, "status", 0))
            http_transport.spool_response_to_file(response, tmp, max_content_bytes=65536)
            http_transport.close_response(response)
            response = None
            try:
                data = http_transport.load_json_file(tmp)
                if not isinstance(data, dict):
                    data = {}
            except (ValueError, TypeError):
                data = {}
            if status != 200:
                fallback = {401: "invalid_token", 403: "insufficient_scope", 409: "stale_plan"}
                raise IntegrationError(status, data.get("code", fallback.get(status, "request_failed")))
            if data.get("schema") != 1:
                raise IntegrationError(status, "unsupported_schema")
            return data
        except IntegrationError:
            raise
        except Exception:
            raise IntegrationError(0, "connection_failed")
        finally:
            http_transport.close_response(response)
            http_transport.remove_file(tmp)

    def get_info(self):
        data = self._json("/info")
        if data.get("serverTime"):
            from .scale_events import use_server_time
            use_server_time(data["serverTime"])
        if data.get("apiVersion") != 1:
            raise IntegrationError(200, "unsupported_api_version")
        return data

    def get_batches(self, phases=("planned", "brewing")):
        self._last_error = None
        try:
            self.get_info()
            result = []
            for row in self._json("/batches").get("batches", []):
                if row.get("phase") in phases and valid_id(row.get("batchId")):
                    batch = Batch(row["batchId"], row.get("name", row["batchId"]))
                    batch.volume_l = row.get("volumeL")
                    batch.phase = row.get("phase")
                    result.append(batch)
            return result
        except Exception as error:
            self._last_error = error if isinstance(error, IntegrationError) else IntegrationError(0, "connection_failed")
            return []

    def get_plan(self, batch_id):
        if not valid_id(batch_id):
            raise IntegrationError(0, "invalid_batch_id")
        data = self._json("/batches/" + batch_id)
        if data.get("batchId") != batch_id or not data.get("planVersion"):
            raise IntegrationError(200, "invalid_plan")
        ids = []
        for row in data.get("items", []):
            if not valid_id(row.get("additionId")) or row["additionId"] in ids:
                raise IntegrationError(200, "invalid_addition")
            ids.append(row["additionId"])
        return data

    @staticmethod
    def context(plan, row=None):
        result = {"batchId": plan["batchId"], "planVersion": plan["planVersion"]}
        if row is not None:
            result["additionId"] = row["additionId"]
        return result

    def get_malts(self, batch_id):
        self._last_error = None
        try:
            plan = self.get_plan(batch_id)
            result = []
            for row in plan.get("items", []):
                grams = mass(row)
                if row.get("category") != "Malz" or grams is None:
                    continue
                item = Malt(row.get("name", "?"), row.get("colorEbc"), grams / 1000)
                item.target_weight_g = grams
                item.context = self.context(plan, row)
                item.ingredient_id = row.get("ingredientId")
                result.append(item)
            return result
        except Exception as error:
            self._last_error = error if isinstance(error, IntegrationError) else IntegrationError(0, "connection_failed")
            return []

    def get_hops_list(self, batch_id):
        self._last_error = None
        try:
            plan = self.get_plan(batch_id)
            # One entry per addition: equal names/timings never collapse IDs.
            return [{"name": row.get("name", "?"),
                     "steps": [(row.get("step") or row.get("use") or "?", mass(row))],
                     "context": self.context(plan, row),
                     "ingredientId": row.get("ingredientId"),
                     "use": row.get("use"), "timeMinutes": row.get("timeMinutes")}
                    for row in plan.get("items", [])
                    if row.get("category") == "Hopfen" and mass(row) is not None]
        except Exception as error:
            self._last_error = error if isinstance(error, IntegrationError) else IntegrationError(0, "connection_failed")
            return []
