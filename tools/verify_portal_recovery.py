"""Regression checks for setup startup and low-memory recovery."""
import sys
import json
import types
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webportal import setup_portal_service as portal, portal_routes, recovery
from netcore.wifi_setup import apply_hostname


class FakeAP:
    def __init__(self):
        self.enabled = True
        self.calls = []
        self.address = ('192.168.4.1', '255.255.255.0', '192.168.4.1', '192.168.4.1')
    def active(self, enabled=None):
        if enabled is not None:
            self.enabled = enabled
            self.calls.append(('active', enabled))
        return self.enabled
    def config(self, **values):
        self.calls.append(('config', values))
    def ifconfig(self, values=None):
        if values:
            self.calls.append(('ifconfig', values))
            self.address = values
        return self.address


class StartupTests(unittest.TestCase):
    def test_portal_constructor_does_not_import_large_html(self):
        with patch.object(portal, '_portal_content', side_effect=MemoryError('HTML heap exhausted')) as html:
            service = portal.SetupPortalService()
        self.assertIsNone(service._listener)
        html.assert_not_called()

    def test_network_and_listener_start_without_html(self):
        service = portal.SetupPortalService()
        order = []
        service._ensure_network = lambda: order.append('network')
        service._start_server_if_needed = lambda: order.append('listener')
        with patch.object(portal, '_portal_content', side_effect=MemoryError()):
            service.start_or_resume()
        self.assertEqual(order, ['network', 'listener'])

    def test_ap_reset_explicit_subnet_and_hostname_driver_error(self):
        ap = FakeAP()
        network = types.SimpleNamespace(AP_IF=1, AUTH_OPEN=0, WLAN=lambda mode: ap,
            hostname=Mock(side_effect=RuntimeError('unsupported hostname operation')))
        service = portal.SetupPortalService()
        with patch.dict(sys.modules, network=network), patch.object(portal, '_sleep_ms'):
            self.assertEqual(service._ensure_ap(), '192.168.4.1')
            self.assertIn(('active', False), ap.calls)
            self.assertIn(('ifconfig', ap.address), ap.calls)
            ap.calls = []
            service._ensure_ap()
            self.assertNotIn(('active', False), ap.calls)

    def test_broken_ap_is_not_reported_as_fictional_ip(self):
        network = types.SimpleNamespace(AP_IF=1, WLAN=Mock(side_effect=OSError('AP failed')))
        service = portal.SetupPortalService()
        with patch.dict(sys.modules, network=network):
            with self.assertRaises(OSError):
                service._ensure_ap()

    def test_ap_without_ip_fails_explicitly(self):
        ap = FakeAP()
        ap.ifconfig = lambda values=None: ('0.0.0.0', '', '', '')
        network = types.SimpleNamespace(AP_IF=1, AUTH_OPEN=0, WLAN=lambda mode: ap, hostname=lambda name: None)
        with patch.dict(sys.modules, network=network), patch.object(portal, '_sleep_ms'):
            with self.assertRaisesRegex(RuntimeError, 'no usable IP'):
                portal.SetupPortalService()._ensure_ap()

    def test_station_retries_stop_before_ap_startup(self):
        order = []
        service = portal.SetupPortalService(wifi_device=types.SimpleNamespace(abandon=lambda: order.append('abandon')))
        service._try_sta = lambda: ''
        service._ensure_ap = lambda: order.append('ap') or '192.168.4.1'
        service._ensure_network()
        self.assertEqual(order, ['abandon', 'ap'])
        self.assertEqual(service.info()['url'], 'http://192.168.4.1:8080/')

    def test_hostname_failure_is_best_effort(self):
        network = types.SimpleNamespace(hostname=Mock(side_effect=RuntimeError()))
        wlan = types.SimpleNamespace(config=Mock(side_effect=RuntimeError()))
        self.assertFalse(apply_hostname(network, wlan))


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.service = portal.SetupPortalService()
        self.responses = []
        self.service._send = lambda client,status=200,content_type='',body='',**kw: self.responses.append((status,body))
        self.service.reboot_after_response = Mock()
        self.values = {'HOSTNAME':'uhs', 'WIFI_SSID':'saved', 'WIFI_PASSWORD':'password123', 'HTTP_INTEGRATION_ENABLED':True}
        self.current = patch.object(portal, '_current_values', return_value=dict(self.values))
        self.current.start()
        self.addCleanup(self.current.stop)

    def request(self, method, target, body=''):
        portal_routes.handle_request(self.service, None, method, target, body)
        return self.responses[-1]

    def test_root_recovers_from_html_memory_error(self):
        with patch.object(portal, 'render_minimal_form_parts', side_effect=MemoryError()):
            status,parts = self.request('GET', '/')
        self.assertEqual(status,200)
        self.assertIn('UHS recovery setup',''.join(parts))

    def test_recovery_and_health_never_load_full_html(self):
        with patch.object(portal, '_portal_content', side_effect=MemoryError()):
            status,parts = self.request('GET','/recovery')
            self.assertIn('recovery/save',''.join(parts))
            status,body = self.request('GET','/health')
            self.assertEqual(json.loads(body),{'ok':True})

    def test_partial_recovery_save_preserves_other_settings(self):
        with patch('storage.config_registry.save_updates', return_value=(True,{})) as save:
            status,parts = self.request('POST','/recovery/save','HOSTNAME=new-name&WIFI_SSID=new&WIFI_PASSWORD=password123&SIMULATION_ENABLED=on')
        self.assertEqual(status,200)
        self.assertEqual(save.call_args.args[0],{'HOSTNAME':'new-name','WIFI_SSID':'new','WIFI_PASSWORD':'password123','SIMULATION_ENABLED':True})
        self.service.reboot_after_response.assert_called_once()

    def test_recovery_respects_authentication(self):
        self.service._cfg['require_token'] = True
        self.service._token = 'test-token'
        self.assertEqual(self.request('GET','/recovery')[0],403)
        self.assertEqual(self.request('POST','/recovery/save','HOSTNAME=x')[0],403)
        status,parts = self.request('GET','/recovery?k=test-token')
        self.assertEqual(status,200)
        self.assertIn("value='test-token'",''.join(parts))

    def test_fallback_escapes_fields_and_errors(self):
        body=''.join(recovery.page({'WIFI_SSID':"'><script>bad</script>"},message='<failure>'))
        self.assertNotIn('<script>',body)
        self.assertIn('&lt;failure&gt;',body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
