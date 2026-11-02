"""Bounded event outbox. Only the worker performs network I/O.

Files are atomically published before transmission. Immutable payloads survive
reboots; rejected results stay on disk for operator investigation.
"""
import os
import time
import math
import json
try:
    import ubinascii as binascii
except ImportError:
    import binascii
import runtime_debug
from ticks import ticks_ms, ticks_diff, ticks_add
from netcore import http_transport

OUTBOX = "storage/scale_events"
MAX_PENDING = 128
MAX_BODY = 16384
_clock_offset = None


def utc_epoch(parts):
    """UTC seconds in the runtime native epoch (1970 or 2000), without TZ assumptions."""
    year, month, day, hour, minute, second = parts[:6]
    def before_year(y):
        y -= 1
        return 365 * y + y // 4 - y // 100 + y // 400
    months = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    days = before_year(year) - before_year(time.gmtime(0)[0])
    days += sum(months[:month - 1]) + day - 1
    if month > 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        days += 1
    return days * 86400 + hour * 3600 + minute * 60 + second


def use_server_time(value):
    """Accept UTC ISO serverTime without changing the device RTC or old events."""
    global _clock_offset
    if not isinstance(value, str) or not value.endswith(("Z", "+00:00")):
        return
    try:
        parts = (int(value[0:4]), int(value[5:7]), int(value[8:10]),
                 int(value[11:13]), int(value[14:16]), int(value[17:19]), 0, 0)
        epoch = utc_epoch(parts)
        _clock_offset = epoch - time.time()
    except (ValueError, TypeError):
        pass


def new_id():
    return binascii.hexlify(os.urandom(16)).decode()


def timestamp():
    now = time.gmtime(time.time() + _clock_offset) if _clock_offset is not None else time.gmtime()
    if now[0] < 2024:
        raise ValueError("Set the UTC device clock before weighing")
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(*now[:6])


def retry_after_seconds(value):
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        pass
    try:
        fields = value.split()
        months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
        clock = fields[4].split(":")
        parts = (int(fields[3]), months.index(fields[2]) + 1, int(fields[1]),
                 int(clock[0]), int(clock[1]), int(clock[2]), 0, 0)
        epoch = utc_epoch(parts)
        return max(0, int(math.ceil(epoch - time.time() - (_clock_offset or 0))))
    except Exception:
        return 0


def _sync():
    sync = getattr(os, "sync", None)
    if sync:
        sync()


class ScaleEvents:
    def __init__(self):
        base = runtime_debug.setting("HTTP_API_BASE_URL", "").rstrip("/")
        self.base_url = base
        self._clock_checked = False
        self._clock_next = ticks_ms()
        self.url = runtime_debug.setting("HTTP_WEBHOOK_URL", "") or (base + "/events" if base else "")
        self.enabled = bool(runtime_debug.setting("HTTP_INTEGRATION_ENABLED", False))
        self.token = runtime_debug.setting("HTTP_API_TOKEN", "")
        self.live_enabled = runtime_debug.setting("HTTP_LIVE_ENABLED", False)
        self.interval = max(1000, int(runtime_debug.setting("HTTP_MEASUREMENT_INTERVAL_MS", 1000)))
        self.error = None
        self._live = None
        self._last_live = None
        self._session = None
        self._sequence = 0
        self._context = {}
        self._running = False
        self._paused = False
        self._suspended = False
        self._busy = False
        self._pending_body = None
        self._sampling = False
        if self.enabled:
            try:
                os.mkdir(OUTBOX)
            except OSError:
                pass
            for name in os.listdir(OUTBOX):
                if name.endswith(".tmp"):
                    path = OUTBOX + "/" + name
                    try:
                        with open(path) as handle:
                            data = json.load(handle)
                        if data.get("eventId") != name[:-4] or data.get("schema") != 1:
                            raise ValueError("Invalid staged event")
                        os.rename(path, path[:-4] + ".json")
                    except Exception:
                        os.rename(path, path[:-4] + ".blocked")
                if name.endswith(".blocked"):
                    self.error = "Rejected result retained: inspect " + name
                    break

    def start(self):
        if not self.enabled:
            return
        if not self.url.startswith(("http://", "https://")):
            self.error = "Configure HTTP API base URL or webhook URL"
            return
        try:
            import _thread
            _thread.start_new_thread(self._worker, ())
        except Exception:
            self.error = "HTTP worker unavailable; results retained locally"

    def begin(self, context=None):
        if not self.enabled:
            return
        self._session = new_id()
        self._sequence = 0
        self._context = dict(context or {})
        self._live = None
        self._last_live = None
        self._sampling = True
        self._pending_body = None

    def suspend(self):
        self._suspended = True
        return not self._busy

    def resume(self):
        self._suspended = False

    def end(self):
        self._sampling = False
        self._live = None

    def sample(self, weight, stable=False):
        if not self.enabled or not self.live_enabled or not self._sampling:
            return
        now = ticks_ms()
        if self._last_live is not None and ticks_diff(now, self._last_live) < self.interval:
            return
        try:
            payload = self._payload("weight", weight, stable)
            payload["sequence"] = self._sequence
            self._sequence += 1
            self._live = json.dumps(payload)
            self._last_live = now
        except Exception as error:
            self.error = str(error)

    def _payload(self, kind, weight, stable):
        if not isinstance(weight, (int, float)) or not math.isfinite(weight):
            raise ValueError("No valid scale reading")
        if weight > 10000000 or weight < (-100000 if kind == "weight" else 0):
            raise ValueError("Weight outside API limits")
        if kind in ("weighing.completed", "filling.completed") and weight <= 0:
            raise ValueError("Completed result requires positive weight")
        payload = dict(self._context)
        payload.update(schema=1, eventId=new_id(), sessionId=self._session or new_id(),
                       type=kind, timestamp=timestamp(), weight=weight, unit="g", stable=bool(stable))
        return payload

    def can_record(self):
        try:
            timestamp()
            if sum(1 for name in os.listdir(OUTBOX) if name.endswith((".json", ".blocked"))) >= MAX_PENDING:
                raise ValueError("Outbox full: deliver or review retained results")
            return True
        except Exception as error:
            self.error = str(error)
            return False

    def complete(self, kind, weight, stable=False, keg_id=None):
        if not self.enabled:
            return True
        try:
            if not self._context.get("batchId") or not self._context.get("planVersion"):
                raise ValueError("Select a batch and weighing plan first")
            if kind == "weighing.completed" and (not stable or not self._context.get("additionId")):
                raise ValueError("Wait for a stable ingredient weight")
            files = os.listdir(OUTBOX)
            if sum(1 for name in files if name.endswith((".json", ".blocked"))) >= MAX_PENDING:
                raise ValueError("Outbox full: deliver or review retained results")
            if self._pending_body is None:
                payload = self._payload(kind, weight, stable)
                if keg_id:
                    payload["kegId"] = keg_id
                self._pending_body = json.dumps(payload)
            body = self._pending_body
            payload = json.loads(body)
            if len(body.encode()) > MAX_BODY:
                raise ValueError("Event exceeds API body limit")
            path = OUTBOX + "/" + payload["eventId"]
            with open(path + ".tmp", "w") as handle:
                handle.write(body)
                handle.flush()
            _sync()
            os.rename(path + ".tmp", path + ".json")
            _sync()
            self.end()
            return True
        except Exception as error:
            self.error = str(error)
            return False

    def _post(self, body):
        client = http_transport.default_requests_module()
        if client is None:
            raise OSError("HTTP client unavailable")
        # No timeout-less compatibility fallback on the background path.
        response = None
        try:
            response = client.post(self.url, data=body,
                                   headers={"Authorization": "Bearer " + self.token,
                                            "Content-Type": "application/json"}, timeout=5)
            status = getattr(response, "status_code", getattr(response, "status", 0))
            # Bound response memory even when the server misbehaves.
            tmp = "scale_event_response.tmp"
            try:
                http_transport.spool_response_to_file(response, tmp, max_content_bytes=MAX_BODY)
                try:
                    data = http_transport.load_json_file(tmp)
                    if not isinstance(data, dict):
                        data = {}
                except (ValueError, TypeError):
                    data = {}
            finally:
                http_transport.remove_file(tmp)
            retry = http_transport.response_header(response, "Retry-After")
            return status, data, retry
        finally:
            http_transport.close_response(response)

    def deliver(self, body):
        """One attempt, exposed for host-side fault-injection tests."""
        try:
            status, data, retry = self._post(body)
            if status in (200, 201) and data.get("schema") == 1 and data.get("accepted") is True:
                if self.error == "HTTP delivery unavailable; results retained locally":
                    self.error = None
                return "accepted", 0
            code = data.get("code", "request_failed")
            if status in (401, 403):
                self._paused = True
                self.error = ("Update API credentials (401)" if status == 401 else
                              "Grant required API scope (403)")
                return "retry", 0
            if status == 429 or status >= 500 or status == 0:
                delay = retry_after_seconds(retry)
                return "retry", delay
            if status in (200, 201):
                return "retry", 0  # Missing acknowledgement: preserve payload.
            self.error = ("Reload changed plan; old result retained (stale_plan)"
                          if code == "stale_plan" else "Review result: HTTP {} {}".format(status, code))
            return "blocked", 0
        except Exception:
            # Transport exception text can contain credentials or URLs.
            self.error = "HTTP delivery unavailable; results retained locally"
            return "retry", 0

    def _worker(self):
        self._running = True
        delay = 1
        wait_until = ticks_ms()
        remaining_wait = 0
        while self._running:
            time.sleep(0.1)
            if self._paused or self._suspended or ticks_diff(ticks_ms(), wait_until) < 0:
                continue
            if remaining_wait > 0:
                chunk = min(3600, remaining_wait)
                remaining_wait -= chunk
                wait_until = ticks_add(ticks_ms(), chunk * 1000)
                continue
            self._busy = True
            try:
                if self._suspended:
                    continue
                if self.base_url and not self._clock_checked and ticks_diff(ticks_ms(), self._clock_next) >= 0:
                    from .generic_http_api import GenericHttpAPI
                    api = GenericHttpAPI()
                    # Avoid the interactive connector's Wi-Fi wait in the worker.
                    client = http_transport.default_requests_module()
                    api._get = lambda url, headers, **kwargs: client.get(url, headers=headers, timeout=5)
                    try:
                        api.get_info()
                        self._clock_checked = True
                    except Exception as error:
                        if getattr(error, "status", 0) in (401, 403):
                            self._paused = True
                            self.error = "Check API credentials and scopes (HTTP {})".format(error.status)
                        self._clock_next = ticks_add(ticks_ms(), 60000)
                    finally:
                        api.close_http()
                    if self._paused:
                        continue
                names = sorted(n for n in os.listdir(OUTBOX) if n.endswith(".json"))
                path = OUTBOX + "/" + names[0] if names else None
                if path:
                    with open(path) as handle:
                        body = handle.read(MAX_BODY + 1)
                else:
                    body = self._live
                    self._live = None
                if not body:
                    continue
                result, retry = self.deliver(body)
                if result == "accepted":
                    if path:
                        os.remove(path)
                        _sync()
                    delay = 1
                elif result == "blocked":
                    if path:
                        os.rename(path, path[:-5] + ".blocked")
                        _sync()
                    delay = 1
                else:
                    delay = min(300, delay * 2)
                # Also bound successful traffic to <= 1 request/s.
                remaining_wait = max(1, retry, delay)
                wait_until = ticks_ms()
            except Exception:
                self.error = "Outbox I/O error; inspect retained files"
                wait_until = ticks_add(ticks_ms(), 5000)
            finally:
                self._busy = False
