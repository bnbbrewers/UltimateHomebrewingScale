import sys
import types
import unittest
from unittest import mock

from webportal import setup_portal_service as portal


class _FakeTime:
    def __init__(self, events):
        self.events = events
        self.now = 1000

    def ticks_ms(self):
        return self.now

    def ticks_add(self, ticks, delta):
        return ticks + delta

    def ticks_diff(self, ticks1, ticks2):
        return ticks1 - ticks2

    def sleep_ms(self, ms):
        self.events.append(("sleep_ms", ms))
        self.now += ms


class _FakeSocket:
    def __init__(self, events):
        self.events = events

    def setsockopt(self, *_args):
        pass

    def bind(self, address):
        self.events.append(("bind", address))

    def listen(self, backlog):
        self.events.append(("listen", backlog))

    def settimeout(self, timeout):
        self.events.append(("settimeout", timeout))


class _EmptyClient:
    def __init__(self, events):
        self.events = events

    def settimeout(self, timeout):
        self.events.append(("client_timeout", timeout))

    def recv(self, _size):
        self.events.append(("recv", 0))
        return b""

    def close(self):
        self.events.append(("client_close",))


class _RequestClient:
    def __init__(self, events, request=b"GET /health HTTP/1.1\r\nHost: scale\r\n\r\n"):
        self.events = events
        self.request = request
        self.sent = b""
        self._read = False

    def setblocking(self, value):
        self.events.append(("client_blocking", value))

    def settimeout(self, timeout):
        self.events.append(("client_timeout", timeout))

    def recv(self, _size):
        if self._read:
            return b""
        self._read = True
        self.events.append(("recv", len(self.request)))
        return self.request

    def send(self, data):
        self.sent += data
        return len(data)

    def close(self):
        self.events.append(("client_close",))


class _RecordingClient(_RequestClient):
    def __init__(self, events, request=b"GET /health HTTP/1.1\r\nHost: scale\r\n\r\n"):
        super().__init__(events, request=request)
        self.send_sizes = []

    def send(self, data):
        self.send_sizes.append(len(data))
        return super().send(data)


class _FailingSendClient(_RequestClient):
    def __init__(self, events, fail_after, request=b"GET /?nocleanup=1 HTTP/1.1\r\nHost: scale\r\n\r\n"):
        super().__init__(events, request=request)
        self.fail_after = fail_after

    def send(self, data):
        if len(self.sent) >= self.fail_after:
            self.events.append(("send_timeout", len(self.sent)))
            raise OSError(116, "ETIMEDOUT")
        return super().send(data)


class _OneClientListener:
    def __init__(self, client):
        self.client = client
        self.done = False

    def accept(self):
        if self.done:
            raise OSError("no pending client")
        self.done = True
        return self.client, ("192.168.4.2", 12345)


class _FakeNetwork(types.SimpleNamespace):
    STA_IF = 0
    AP_IF = 1

    def __init__(self, events):
        super().__init__(STA_IF=self.STA_IF, AP_IF=self.AP_IF)
        self.events = events

    def WLAN(self, interface):
        events = self.events

        class WLAN:
            def __init__(self, interface):
                self.interface = interface
                self._active = False

            def isconnected(self):
                return False

            def active(self, value=None):
                if value is None:
                    return self._active
                self._active = bool(value)
                events.append(("active", self.interface, self._active))

            def config(self, **kwargs):
                events.append(("config", self.interface, kwargs))

            def ifconfig(self):
                return ("192.168.4.1", "255.255.255.0", "192.168.4.1", "8.8.8.8")

        return WLAN(interface)


class SetupPortalServiceTests(unittest.TestCase):
    def test_minimal_form_uses_update_channel_not_branch(self):
        html = portal.render_minimal_form_html({"UPDATE_CHANNEL": "prerelease"})

        self.assertIn("Release channel", html)
        self.assertIn("name='UPDATE_CHANNEL'", html)
        self.assertIn("<option value='prerelease' selected>prerelease</option>", html)
        self.assertNotIn("UPDATE_BRANCH", html)
        self.assertNotIn("Update branch", html)

    def test_minimal_current_values_defaults_update_channel_to_stable(self):
        old_config = sys.modules.get("config")
        sys.modules["config"] = types.SimpleNamespace()
        try:
            with mock.patch(
                "storage.config_registry.load_current_values",
                side_effect=RuntimeError("registry unavailable"),
            ):
                values = portal._current_values()
        finally:
            if old_config is None:
                sys.modules.pop("config", None)
            else:
                sys.modules["config"] = old_config

        self.assertEqual(values["UPDATE_CHANNEL"], "stable")
        self.assertNotIn("UPDATE_BRANCH", values)

    def test_current_values_uses_config_registry_so_wifi_can_come_from_nvs(self):
        expected = {
            "LANGUAGE": "en",
            "WIFI_SSID": "nvs_wifi",
            "WIFI_PASSWORD": "nvs_secret",
        }

        with mock.patch(
            "storage.config_registry.load_current_values",
            return_value=expected,
        ) as load_current_values:
            values = portal._current_values()

        load_current_values.assert_called_once_with()
        self.assertEqual(values["WIFI_SSID"], "nvs_wifi")
        self.assertEqual(values["WIFI_PASSWORD"], "nvs_secret")

    def test_ap_mode_waits_for_network_to_settle_before_listening(self):
        events = []
        fake_network = _FakeNetwork(events)
        fake_socket_module = types.SimpleNamespace(
            AF_INET=2,
            SOCK_STREAM=1,
            SOL_SOCKET=1,
            SO_REUSEADDR=2,
            socket=lambda *_args: _FakeSocket(events),
        )
        old_network = sys.modules.get("network")
        old_socket = sys.modules.get("socket")
        old_time = portal.time
        sys.modules["network"] = fake_network
        sys.modules["socket"] = fake_socket_module
        portal.time = _FakeTime(events)
        try:
            service = portal.SetupPortalService(wifi_device=None)
            info = service.start_or_resume()
        finally:
            if old_network is None:
                sys.modules.pop("network", None)
            else:
                sys.modules["network"] = old_network
            if old_socket is None:
                sys.modules.pop("socket", None)
            else:
                sys.modules["socket"] = old_socket
            portal.time = old_time

        expected_settle_ms = 300
        self.assertEqual("ap", info["mode"])
        self.assertIn(("sleep_ms", expected_settle_ms), events)
        self.assertLess(
            events.index(("sleep_ms", expected_settle_ms)),
            events.index(("bind", (portal.PORTAL_HTTP_HOST, portal.PORTAL_HTTP_PORT))),
        )

    def test_empty_connection_does_not_release_screen_memory(self):
        events = []
        cleanup_calls = []
        service = portal.SetupPortalService(
            wifi_device=None,
            before_client=lambda: cleanup_calls.append("cleanup"),
        )
        service._listener = _OneClientListener(_EmptyClient(events))

        service.tick()

        self.assertEqual([], cleanup_calls)
        self.assertIn(("recv", 0), events)

    def test_screen_memory_is_released_only_once_for_real_requests(self):
        events = []
        cleanup_calls = []
        service = portal.SetupPortalService(
            wifi_device=None,
            before_client=lambda: cleanup_calls.append("cleanup"),
        )

        service._listener = _OneClientListener(
            _RequestClient(events, request=b"GET / HTTP/1.1\r\nHost: scale\r\n\r\n")
        )
        service.tick()
        service._listener = _OneClientListener(
            _RequestClient(events, request=b"GET / HTTP/1.1\r\nHost: scale\r\n\r\n")
        )
        service.tick()

        self.assertEqual(["cleanup"], cleanup_calls)

    def test_response_waits_for_socket_drain_before_close(self):
        events = []
        old_time = portal.time
        portal.time = _FakeTime(events)
        try:
            service = portal.SetupPortalService(wifi_device=None)
            client = _RequestClient(events)
            service._listener = _OneClientListener(client)

            service.tick()
        finally:
            portal.time = old_time

        expected_drain_ms = 200
        self.assertIn(("sleep_ms", expected_drain_ms), events)
        self.assertLess(
            events.index(("sleep_ms", expected_drain_ms)),
            events.index(("client_close",)),
        )

    def test_diag_route_does_not_release_screen_memory(self):
        events = []
        cleanup_calls = []
        client = _RequestClient(events, request=b"GET /diag HTTP/1.1\r\nHost: scale\r\n\r\n")
        service = portal.SetupPortalService(
            wifi_device=None,
            before_client=lambda: cleanup_calls.append("cleanup"),
        )
        service._listener = _OneClientListener(client)

        service.tick()

        self.assertEqual([], cleanup_calls)
        self.assertIn(b"UHS diag OK", client.sent)

    def test_root_nocleanup_query_skips_screen_memory_release(self):
        events = []
        cleanup_calls = []
        client = _RequestClient(events, request=b"GET /?nocleanup=1 HTTP/1.1\r\nHost: scale\r\n\r\n")
        service = portal.SetupPortalService(
            wifi_device=None,
            before_client=lambda: cleanup_calls.append("cleanup"),
        )
        service._listener = _OneClientListener(client)

        service.tick()

        self.assertEqual([], cleanup_calls)
        self.assertIn(b"UHS setup", client.sent)

    def test_large_response_is_sent_in_small_chunks(self):
        events = []
        client = _RecordingClient(
            events,
            request=b"GET /?nocleanup=1 HTTP/1.1\r\nHost: scale\r\n\r\n",
        )
        old_time = portal.time
        portal.time = _FakeTime(events)
        try:
            service = portal.SetupPortalService(wifi_device=None)
            service._listener = _OneClientListener(client)
            service.tick()
        finally:
            portal.time = old_time

        self.assertTrue(client.send_sizes)
        self.assertLessEqual(max(client.send_sizes), 256)

    def test_send_timeout_does_not_attempt_error_response_on_same_socket(self):
        events = []
        client = _FailingSendClient(events, fail_after=300)
        service = portal.SetupPortalService(wifi_device=None)
        service._listener = _OneClientListener(client)

        service.tick()

        self.assertEqual(1, len([event for event in events if event[0] == "send_timeout"]))

    def test_diag_bytes_route_returns_requested_payload_size(self):
        events = []
        client = _RequestClient(events, request=b"GET /diag?bytes=777 HTTP/1.1\r\nHost: scale\r\n\r\n")
        service = portal.SetupPortalService(wifi_device=None)
        service._listener = _OneClientListener(client)

        service.tick()

        header, _sep, body = client.sent.partition(b"\r\n\r\n")
        self.assertIn(b"Content-Length: 777", header)
        self.assertEqual(777, len(body))

    def test_diag_html_route_returns_html_payload(self):
        events = []
        client = _RequestClient(events, request=b"GET /diag?html=777 HTTP/1.1\r\nHost: scale\r\n\r\n")
        service = portal.SetupPortalService(wifi_device=None)
        service._listener = _OneClientListener(client)

        service.tick()

        header, _sep, body = client.sent.partition(b"\r\n\r\n")
        self.assertIn(b"Content-Type: text/html; charset=utf-8", header)
        self.assertIn(b"Content-Length: 777", header)
        self.assertEqual(777, len(body))

    def test_diag_form_text_route_returns_form_as_plain_text(self):
        events = []
        client = _RequestClient(events, request=b"GET /diag?formtext=1 HTTP/1.1\r\nHost: scale\r\n\r\n")
        service = portal.SetupPortalService(wifi_device=None)
        service._listener = _OneClientListener(client)

        service.tick()

        header, _sep, body = client.sent.partition(b"\r\n\r\n")
        self.assertIn(b"Content-Type: text/plain; charset=utf-8", header)
        self.assertIn(b"UHS setup", body)


if __name__ == "__main__":
    unittest.main()
