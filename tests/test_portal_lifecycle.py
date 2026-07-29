import inspect
import unittest

from apps.settings_app import SettingsApp
from webportal.setup_portal_service import SetupPortalService


class _Client:
    def __init__(self, events, request):
        self.events = events
        self.request = request
        self._read = False

    def setblocking(self, _value):
        pass

    def settimeout(self, _value):
        pass

    def recv(self, _size):
        if self._read:
            return b""
        self._read = True
        return self.request

    def send(self, data):
        self.events.append("send")
        return len(data)

    def close(self):
        self.events.append("close")


class _Listener:
    def __init__(self, client):
        self._client = client

    def accept(self):
        client = self._client
        self._client = None
        if client is None:
            raise OSError("empty")
        return client, ("192.168.4.2", 12345)


class _Button:
    def was_long_pressed(self):
        return False


class _Hardware:
    def __init__(self):
        self.button = _Button()
        self.wifi = object()


class _ScreenManager:
    def __init__(self):
        self.cleanup_calls = []

    def memory_cleanup(self, keep_ids=(), loading_message=None, loading_color=0x333333):
        self.cleanup_calls.append((keep_ids, loading_message, loading_color))


class _I18n:
    def t(self, key):
        return key


class _PortalWithInitialPageEvent:
    def __init__(self, events):
        self.events = events

    def tick(self):
        self.events.append("portal_tick")

    def consume_events(self):
        self.events.append("events_consumed")
        return ("INITIAL_PAGE_SERVED",)


class PortalLifecycleTests(unittest.TestCase):
    def test_initial_page_event_is_published_after_client_close(self):
        events = []
        service = SetupPortalService(wifi_device=None)
        service._listener = _Listener(
            _Client(events, b"GET /?nocleanup=1 HTTP/1.1\r\nHost: scale\r\n\r\n")
        )

        service.tick()

        self.assertEqual(service.consume_events(), ("INITIAL_PAGE_SERVED",))
        self.assertLess(events.index("send"), events.index("close"))

    def test_service_has_no_ui_callback_parameter(self):
        self.assertNotIn("before_client", inspect.signature(SetupPortalService).parameters)

    def test_settings_releases_qr_screen_after_portal_tick_event(self):
        events = []
        screen_manager = _ScreenManager()
        app = SettingsApp(screen_manager, _Hardware(), {}, i18n=_I18n())
        app._portal = _PortalWithInitialPageEvent(events)

        app.tick()

        self.assertEqual(events, ["portal_tick", "events_consumed"])
        self.assertEqual(
            screen_manager.cleanup_calls,
            [((), "settings.portal_in_progress", 0x7E57C2)],
        )


if __name__ == "__main__":
    unittest.main()
