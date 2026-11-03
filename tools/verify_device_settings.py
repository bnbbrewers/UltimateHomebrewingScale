"""Device-settings regressions: python tools/verify_device_settings.py."""
import sys
import json
import types
import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import simulation
from netcore import wifi_setup
from storage import config_registry
from webportal import device_routes, portal_html, setup_portal_service


class FakeWlan:
    def __init__(self):
        self.link = False
        self.on = False
        self.status_value = 1
        self.calls = []
        self.rows = []
    def active(self, value=None):
        if value is not None:
            self.on = value
        return self.on
    def connect(self, ssid, password):
        self.calls.append(('connect', ssid, password))
    def disconnect(self):
        self.link = False
        self.calls.append(('disconnect',))
    def isconnected(self):
        return self.link
    def ifconfig(self):
        return ('192.168.1.42', '255.255.255.0', '192.168.1.1', '192.168.1.1')
    def status(self, key=None):
        return -55 if key == 'rssi' else self.status_value
    def scan(self):
        return self.rows


def network_for(wlan):
    return types.SimpleNamespace(STA_IF=0, AP_IF=1, STAT_WRONG_PASSWORD=-3,
        STAT_NO_AP_FOUND=-2, STAT_CONNECT_FAIL=-1, WLAN=lambda interface: wlan,
        hostname=Mock())


class WifiTests(unittest.TestCase):
    def setUp(self):
        self.wlan = FakeWlan()
        self.net = network_for(self.wlan)
        self.patch = patch.dict(sys.modules, network=self.net)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_hostname_validation(self):
        for name in ('my-scale', 'UHS1', 'x', 'x'*32):
            self.assertTrue(config_registry.validate_payload({'HOSTNAME': name})[0])
        for name in ('', '-uhs', 'uhs-', 'a.local', 'has space', 'ümlaut', 'a'*33, 'a\n'):
            self.assertFalse(config_registry.validate_payload({'HOSTNAME': name})[0])
        self.assertEqual(config_registry.validate_payload({'HOSTNAME': 'UHS1'})[1]['HOSTNAME'], 'uhs1')

    def test_hostname_global_and_older_firmware_fallback(self):
        with patch('runtime_debug.setting', return_value='my-scale'):
            self.assertTrue(wifi_setup.apply_hostname(self.net, self.wlan))
            self.net.hostname.assert_called_once_with('my-scale')
            self.net.hostname.side_effect = AttributeError()
            self.wlan.config = Mock()
            self.assertTrue(wifi_setup.apply_hostname(self.net, self.wlan))
            self.wlan.config.assert_called_once_with(dhcp_hostname='my-scale')

    def test_scan_deduplicates_strongest_and_sorts(self):
        self.wlan.rows = [(b'Same', b'', 1, -80, 3, False),
                          (b'Same', b'', 6, -40, 3, False),
                          (b'Open', b'', 11, -60, 0, False),
                          (b'', b'', 1, -20, 3, True)]
        result = wifi_setup.scan_networks(self.wlan)
        self.assertEqual([r['ssid'] for r in result], ['Same', 'Open'])
        self.assertEqual(result[0]['rssi'], -40)
        self.assertFalse(result[1]['secure'])

    def test_utf8_ssid_and_password_validation(self):
        self.assertFalse(config_registry.validate_payload({'WIFI_SSID': 'ü'*17})[0])
        self.assertTrue(config_registry.validate_payload({'WIFI_SSID': 'ü'*16})[0])
        self.assertFalse(config_registry.validate_payload({'WIFI_PASSWORD': 'short'})[0])
        self.assertTrue(config_registry.validate_payload({'WIFI_PASSWORD': ''})[0])
        self.assertTrue(config_registry.validate_payload({'WIFI_PASSWORD': 'a'*64})[0])
        self.assertFalse(config_registry.validate_payload({'WIFI_PASSWORD': 'z'*64})[0])

    def test_nonblocking_test_success_and_restore(self):
        wifi = types.SimpleNamespace(use_station=Mock())
        test = wifi_setup.ConnectionTest(self.wlan, ('saved', 'old-password'), wifi)
        test.start('candidate', 'new-password')
        self.assertTrue(test.running)
        self.assertTrue(wifi._portal_test)
        self.wlan.link = True
        test.tick()
        self.assertFalse(test.running)
        self.assertEqual(test.result, 'connected')
        self.assertEqual(test.status()['ip'], '192.168.1.42')
        test.restore()
        self.assertIn(('connect', 'saved', 'old-password'), self.wlan.calls)

    def test_wrong_password_restores_saved_network(self):
        test = wifi_setup.ConnectionTest(self.wlan, ('saved', 'old-password'))
        test.start('candidate', 'bad-password')
        self.wlan.status_value = -3
        test.tick()
        self.assertEqual(test.result, 'wrong_password')
        self.assertEqual(self.wlan.calls[-1], ('connect', 'saved', 'old-password'))
        self.assertNotIn('bad-password', json.dumps(test.status()))

    def test_timeout_restores_and_second_test_is_rejected(self):
        test = wifi_setup.ConnectionTest(self.wlan, ('saved', 'old-password'))
        with patch('netcore.wifi_setup.ticks_ms', return_value=0):
            test.start('candidate', 'new-password')
        with self.assertRaises(ValueError):
            test.start('another', 'new-password')
        with patch('netcore.wifi_setup.ticks_ms', return_value=20001):
            test.tick()
        self.assertEqual(test.result, 'timeout')
        self.assertFalse(test.running)

    def test_cached_connection_loss_is_detected_and_test_is_not_interrupted(self):
        spec = importlib.util.spec_from_file_location('_wifi_test_module', ROOT/'devices/wifi.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        wifi = module.WifiDevice()
        wifi._wlan = self.wlan
        wifi._done = True
        self.assertFalse(wifi.connected())
        wifi._portal_test = True
        wifi._start_connect = Mock(side_effect=AssertionError('must not reconnect during test'))
        wifi.tick()
        self.assertFalse(wifi.ensure_connected())


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.timer = patch('simulation.ticks_ms', side_effect=lambda: self.now)
        self.timer.start()
        self.addCleanup(self.timer.stop)
        self.scale = simulation.SimulatedScale()

    def test_ramp_stops_at_target_and_becomes_stable(self):
        self.scale.set_target(250)
        self.scale.tare()
        self.now = 1000
        self.assertEqual(self.scale.read_weight_filtered(), 100)
        self.now = 4000
        self.assertEqual(self.scale.read_weight_filtered(), 250)
        for self.now in range(4100, 4700, 100):
            self.scale.read_weight_filtered()
        self.assertTrue(self.scale.is_stable())

    def test_small_recipe_target_is_not_overshot(self):
        self.scale.set_target(0.2)
        self.now = 1000
        self.assertEqual(self.scale.read_weight_filtered(), 0.2)

    def test_fixed_mode_places_load_after_tare(self):
        self.scale.mode = 'fixed'
        self.scale.set_target(42)
        self.scale.tare()
        self.assertEqual(self.scale.read_weight_filtered(), 0)
        self.now = 600
        self.assertEqual(self.scale.read_weight_filtered(), 42)

    def test_live_set_tare_and_invalid_values(self):
        self.scale.set_weight(-20)
        self.assertEqual(self.scale.read_weight_filtered(), -20)
        for value in ('nan', 'inf', -100001, 10000001):
            with self.assertRaises(ValueError):
                self.scale.set_weight(value)
        self.scale.tare()
        self.assertEqual(self.scale.read_weight_filtered(), 0)

    def test_virtual_relay_pauses_filling_and_resumes_same_weight(self):
        relay = simulation.SimulatedRelay(self.scale)
        self.scale.prepare_fill(3000, 2000)
        self.now = 1000
        self.assertEqual(self.scale.read_weight_filtered(), 3000)
        relay.set_on()
        self.now = 2000
        self.assertEqual(self.scale.read_weight_filtered(), 3100)
        relay.set_off()
        self.now = 5000
        self.assertEqual(self.scale.read_weight_filtered(), 3100)
        self.scale.prepare_fill(3000, 2000, resume=True)
        relay.set_on()
        self.now = 6000
        self.assertEqual(self.scale.read_weight_filtered(), 3200)
        self.assertTrue(relay.simulated)

    def test_tare_returns_to_normal_weighing_after_fill(self):
        self.scale.prepare_fill(3000, 2000)
        self.scale.tare()
        self.scale.set_target(500)
        self.now = 1000
        self.assertEqual(self.scale.read_weight_filtered(), 100)

    def test_hardware_manager_never_constructs_physical_scale_or_relay(self):
        scale = Mock(side_effect=AssertionError('physical scale constructed'))
        relay = Mock(side_effect=AssertionError('physical relay constructed'))
        m5 = types.ModuleType('M5'); m5.BtnA = object()
        modules = {
            'M5': m5,
            'devices.scale': types.SimpleNamespace(CalibratedScale=scale),
            'devices.relay': types.SimpleNamespace(RelayDevice=relay),
            'devices.wifi': types.SimpleNamespace(WifiDevice=lambda **kw: None),
            'devices.button': types.SimpleNamespace(ButtonDevice=lambda *a,**kw: None),
            'devices.rotary': types.SimpleNamespace(RotaryDevice=lambda: None),
        }
        spec = importlib.util.spec_from_file_location('_hardware_test_module', ROOT/'core/hardware_manager.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,modules), patch('runtime_debug.setting',side_effect=lambda k,d=None: True if k=='SIMULATION_ENABLED' else d):
            spec.loader.exec_module(module)
            hardware = module.HardwareManager()
            self.assertTrue(hardware.scale.simulated)
            hardware.relay.set_on()
            self.assertTrue(hardware.relay.is_on())
        scale.assert_not_called()
        relay.assert_not_called()

    def test_simulation_defaults_do_not_send_events(self):
        # Inspect the factory in isolation from M5/LVGL imports.
        spec = importlib.util.spec_from_file_location('_factory_test_module', ROOT/'core/api_factory.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        values = {'SIMULATION_ENABLED': True, 'HTTP_INTEGRATION_ENABLED': True}
        with patch('runtime_debug.setting', side_effect=lambda k,d=None: values.get(k,d)):
            self.assertIsNone(module.ApiFactory().get('events'))


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.responses = []
        self.service = types.SimpleNamespace(_scale=simulation.SimulatedScale(), _wifi_test=None,
            _cfg={'ap_ssid':'UHS-Setup'}, _wifi=None, _ap=types.SimpleNamespace(active=lambda: True),
            _send=lambda client,status,ctype,body: self.responses.append((status,json.loads(body))),
            _token_ok=lambda query,form: True, _ensure_ap=Mock(return_value='192.168.4.1'))
        self.portal = types.SimpleNamespace(parse_form_urlencoded=setup_portal_service.parse_form_urlencoded,
            _current_values=lambda: {'WIFI_SSID':'saved','WIFI_PASSWORD':'old-password'},
            build_portal_url=setup_portal_service.build_portal_url, PORTAL_HTTP_PORT=8080)

    def call(self, method, path, body=''):
        device_routes.handle(self.service, None, method, path, {}, body, self.portal)
        return self.responses[-1]

    def test_simulation_preview_and_control(self):
        self.assertEqual(self.call('POST','/simulation/weight','weight=123&action=set')[0], 200)
        self.assertEqual(self.call('GET','/simulation/status')[1]['weightG'],123)

    def test_real_scale_cannot_be_overwritten(self):
        self.service._scale = types.SimpleNamespace(set_weight=Mock())
        self.assertEqual(self.call('POST','/simulation/weight','weight=123')[0],400)
        self.service._scale.set_weight.assert_not_called()

    def test_authentication_is_required_for_scan_test_and_simulation(self):
        self.service._token_ok = lambda *args: False
        for method,path in [('POST','/wifi/scan'),('POST','/wifi/test'),('GET','/wifi/status'),('POST','/simulation/weight')]:
            self.assertEqual(self.call(method,path)[0],403)
        self.service._ensure_ap.assert_not_called()

    def test_invalid_credentials_do_not_change_radio_or_storage(self):
        with patch('storage.config_registry.save_updates') as save:
            status,data = self.call('POST','/wifi/test','WIFI_SSID=test&WIFI_PASSWORD=x')
        self.assertEqual(status,400)
        self.service._ensure_ap.assert_not_called()
        save.assert_not_called()

    def test_unavailable_recovery_ap_prevents_disconnection(self):
        self.service._ap = None
        wlan = FakeWlan()
        with patch.dict(sys.modules,network=network_for(wlan)):
            status,data = self.call('POST','/wifi/test','WIFI_SSID=test&WIFI_PASSWORD=password123')
        self.assertEqual(status,503)
        self.assertEqual(wlan.calls,[])

    def test_connection_test_creates_recovery_ap_and_does_not_save(self):
        wlan = FakeWlan()
        with patch.dict(sys.modules,network=network_for(wlan)), patch('storage.config_registry.save_updates') as save:
            status,data = self.call('POST','/wifi/test','WIFI_SSID=test&WIFI_PASSWORD=password123')
        self.assertEqual(status,200)
        self.service._ensure_ap.assert_called_once()
        save.assert_not_called()
        self.assertNotIn('password123',json.dumps(data))
        self.assertEqual(wlan.calls[-1],('connect','test','password123'))

    def test_form_has_network_suggestions_and_explicit_simulation_controls(self):
        values={key:spec['default'] for key,spec in config_registry.EDITABLE_KEYS.items()}
        html=portal_html.render_form_html(values)
        for text in ("name='HOSTNAME'", "list='wifi-list'", "id='wifi-test'", "id='sim-set'", 'SIMULATION_SEND_EVENTS', '/wifi/scan'):
            self.assertIn(text,html)
        self.assertEqual(html.count("name='HOSTNAME'"),1)
        self.assertEqual(html.count('<script>'),1)
        self.assertIn('physical relay',html)


if __name__ == '__main__':
    unittest.main(verbosity=2)
