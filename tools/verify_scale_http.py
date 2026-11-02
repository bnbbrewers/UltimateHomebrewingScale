"""Run with python tools/verify_scale_http.py. No M5/LVGL or network required."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
import io
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.generic_http_api import GenericHttpAPI, IntegrationError, mass
from api import scale_events as events
from apps.recipe_app import RecipeApp
from apps.keg_filler_app import KegFillerApp, _STATE_FILLING_DONE_ACK
from storage import config_registry
from webportal import portal_html
from tools.build_runtime import include_runtime_path
from updater.tar_extract import _safe_path

PLAN = {'schema': 1, 'batchId': 'batch-1', 'planVersion': 'sha256:old', 'items': [
    {'additionId': 'malt-1', 'ingredientId': 'malt', 'category': 'Malz', 'name': 'Pale', 'unit': 'kg', 'targetWeightG': 4000.2, 'colorEbc': None},
    {'additionId': 'hop-1', 'ingredientId': 'hop', 'category': 'Hopfen', 'name': 'Same', 'unit': 'g', 'targetWeightG': 0.2, 'step': 'Boil 60', 'timeMinutes': 60},
    {'additionId': 'hop-2', 'ingredientId': 'hop', 'category': 'Hopfen', 'name': 'Same', 'unit': 'g', 'targetWeightG': 20, 'step': 'Boil 10', 'timeMinutes': 10},
    {'additionId': 'hop-3', 'ingredientId': 'hop', 'category': 'Hopfen', 'name': 'Same', 'unit': 'g', 'targetWeightG': 30, 'step': 'Boil 10', 'timeMinutes': 10},
    {'additionId': 'unknown', 'category': 'Malz', 'unit': 'pieces', 'targetWeightG': None},
]}
CONTEXT = {'batchId': 'batch-1', 'planVersion': 'sha256:old', 'additionId': 'hop-2'}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.api = GenericHttpAPI()
        self.api._json = lambda path: copy.deepcopy(PLAN)

    def test_unknown_mass_and_colour(self):
        malts = self.api.get_malts('batch-1')
        self.assertEqual(len(malts), 1)
        self.assertIsNone(malts[0].ebc)
        self.assertEqual(malts[0].target_weight_g, 4000.2)
        for value in (None, float('nan'), float('inf'), True, -1):
            self.assertIsNone(mass({'unit': 'g', 'targetWeightG': value}))
        self.assertIsNone(mass({'unit': 'L', 'targetWeightG': 1000}))

    def test_separate_hop_additions_survive_removal(self):
        hops = self.api.get_hops_list('batch-1')
        self.assertEqual([h['context']['additionId'] for h in hops], ['hop-1', 'hop-2', 'hop-3'])
        self.assertEqual(hops[0]['steps'][0][1], 0.2)
        hops.pop(1)
        self.assertEqual(hops[1]['context']['additionId'], 'hop-3')
        self.assertEqual(hops[1]['timeMinutes'], 10)
        self.assertEqual(hops[1]['context']['planVersion'], 'sha256:old')

    def test_invalid_batch_path_and_duplicate_additions(self):
        with self.assertRaises(IntegrationError):
            self.api.get_plan('../bad')
        bad = copy.deepcopy(PLAN)
        bad['items'][1]['additionId'] = 'malt-1'
        self.api._json = lambda path: bad
        self.assertEqual(self.api.get_malts('batch-1'), [])
        self.assertEqual(self.api.last_error.code, 'invalid_addition')

    def test_batch_phase_filter(self):
        self.api.get_info = lambda: {}
        self.api._json = lambda p: {'batches': [
            {'batchId': phase, 'phase': phase, 'name': phase}
            for phase in ('planned', 'brewing', 'fermenting', 'packaging')]}
        self.assertEqual([b.batch_id for b in self.api.get_batches()], ['planned', 'brewing'])
        self.assertEqual([b.batch_id for b in self.api.get_batches(('packaging',))], ['packaging'])

    def test_response_closed_on_http_error(self):
        response = types.SimpleNamespace(status_code=401, content=b'{"code":"invalid_token"}', close=lambda: None)
        self.api = GenericHttpAPI()
        self.api.base_url = 'http://example.invalid/api'
        self.api._get = lambda *a, **k: response
        with patch('api.generic_http_api.http_transport.close_response') as close:
            with self.assertRaises(IntegrationError) as error:
                self.api.get_info()
            self.assertEqual(error.exception.code, 'invalid_token')
            self.assertIn(unittest.mock.call(response), close.call_args_list)


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.previous = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.previous)
        os.mkdir('storage')
        self.settings = {'HTTP_INTEGRATION_ENABLED': True, 'HTTP_API_BASE_URL': 'http://example.invalid/api', 'HTTP_LIVE_ENABLED': True}
        self.patch = patch('runtime_debug.setting', side_effect=lambda key, default=None: self.settings.get(key, default))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(setattr, events, '_clock_offset', None)
        self.service = events.ScaleEvents()
        self.service.begin(CONTEXT)

    def payload(self):
        paths = list(Path(events.OUTBOX).glob('*.json'))
        self.assertEqual(len(paths), 1)
        return paths[0].read_text()

    def test_persistence_reboot_lost_response_and_duplicate_ack(self):
        self.assertTrue(self.service.complete('weighing.completed', 20, True))
        body = self.payload()
        rebooted = events.ScaleEvents()
        calls = []
        def post(data):
            calls.append(data)
            if len(calls) == 1:
                raise OSError('lost response with secret')
            return 200, {'schema': 1, 'accepted': True, 'duplicate': True}, ''
        rebooted._post = post
        self.assertEqual(rebooted.deliver(body)[0], 'retry')
        self.assertNotIn('secret', rebooted.error)
        self.assertEqual(rebooted.deliver(body)[0], 'accepted')
        self.assertEqual(calls, [body, body])
        data = json.loads(body)
        self.assertEqual(data['planVersion'], 'sha256:old')
        self.assertNotIn('deviceId', data)

    def run_worker(self, service, steps=30):
        service._clock_checked = True
        now = [1000]
        count = [0]
        def advance(_seconds):
            now[0] += 1000
            count[0] += 1
            if count[0] >= steps:
                service._running = False
        with patch('api.scale_events.time.sleep', side_effect=advance), patch('api.scale_events.ticks_ms', side_effect=lambda: now[0]):
            service._worker()

    def test_worker_retries_and_drains_after_reboot(self):
        self.assertTrue(self.service.complete('weighing.completed', 20, True))
        original = self.payload()
        rebooted = events.ScaleEvents()
        calls = []
        def post(body):
            calls.append(body)
            if len(calls) == 1:
                raise OSError('lost acknowledgement')
            return 200, {'schema': 1, 'accepted': True, 'duplicate': True}, ''
        rebooted._post = post
        self.run_worker(rebooted)
        self.assertEqual(calls, [original, original])
        self.assertEqual(os.listdir(events.OUTBOX), [])

    def test_worker_retains_stale_plan_without_rewriting(self):
        self.assertTrue(self.service.complete('weighing.completed', 20, True))
        original = self.payload()
        self.service._post = lambda body: (409, {'code': 'stale_plan'}, '')
        self.run_worker(self.service)
        files = list(Path(events.OUTBOX).glob('*.blocked'))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_text(), original)
        rebooted = events.ScaleEvents()
        self.assertIn('Rejected result', rebooted.error)

    def test_worker_stops_after_revoked_credentials(self):
        self.assertTrue(self.service.complete('weighing.completed', 20, True))
        calls = []
        def post(body):
            calls.append(body)
            return 401, {'code': 'invalid_token'}, ''
        self.service._post = post
        self.run_worker(self.service)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(list(Path(events.OUTBOX).glob('*.json'))), 1)

    def test_suspended_worker_performs_no_http(self):
        self.service._suspended = True
        self.service._post = lambda body: self.fail('HTTP during local filling')
        self.assertTrue(self.service.complete('weighing.completed', 20, True))
        self.run_worker(self.service)
        self.assertTrue(self.payload())

    def test_post_uses_bearer_json_timeout_and_closes_response(self):
        response = types.SimpleNamespace(status_code=201, headers={},
            raw=io.BytesIO(b'{"schema":1,"accepted":true}'), close=unittest.mock.Mock())
        client = types.SimpleNamespace(post=unittest.mock.Mock(return_value=response))
        self.service.token = 'opaque-secret'
        with patch('api.scale_events.http_transport.default_requests_module', return_value=client):
            status, data, retry = self.service._post('{"weight":20}')
        self.assertEqual(status, 201)
        self.assertTrue(data['accepted'])
        kwargs = client.post.call_args.kwargs
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer opaque-secret')
        self.assertEqual(kwargs['headers']['Content-Type'], 'application/json')
        self.assertEqual(kwargs['timeout'], 5)
        self.assertNotIn('opaque-secret', kwargs['data'])
        response.close.assert_called_once()

    def test_auth_scope_and_stale_plan(self):
        for status in (401, 403):
            self.service._paused = False
            self.service._post = lambda body: (status, {}, '')
            self.assertEqual(self.service.deliver('{}')[0], 'retry')
            self.assertTrue(self.service._paused)
            self.assertIn(str(status), self.service.error)
        self.service._post = lambda body: (409, {'code': 'stale_plan'}, '')
        self.assertEqual(self.service.deliver('{}')[0], 'blocked')
        self.assertIn('stale_plan', self.service.error)

    def test_retry_after_and_server_errors(self):
        for status in (429, 500, 503):
            self.service._post = lambda body: (status, {}, '600')
            self.assertEqual(self.service.deliver('{}'), ('retry', 600))
        self.service._post = lambda body: (200, {}, '')
        self.assertEqual(self.service.deliver('{}')[0], 'retry')
        self.assertEqual(events.retry_after_seconds('bad'), 0)
        self.assertEqual(events.retry_after_seconds('12'), 12)
        with patch('api.scale_events.time.time', return_value=0):
            self.assertEqual(events.retry_after_seconds('Thu, 01 Jan 1970 00:01:00 GMT'), 60)

    def test_live_stream_is_bounded_and_not_persisted(self):
        self.settings['HTTP_MEASUREMENT_INTERVAL_MS'] = 1
        self.service = events.ScaleEvents()
        self.service.begin()
        with patch('api.scale_events.ticks_ms', side_effect=[1000, 1001, 2000]):
            self.service.sample(1)
            first = self.service._live
            self.service.sample(2)
            self.assertEqual(self.service._live, first)
            self.service.sample(3)
        self.assertEqual(json.loads(self.service._live)['sequence'], 1)
        self.assertEqual(json.loads(self.service._live)['weight'], 3)
        self.assertEqual(os.listdir(events.OUTBOX), [])
        self.service.end()
        self.assertIsNone(self.service._live)

    def test_no_unstable_or_unbound_results(self):
        self.assertFalse(self.service.complete('weighing.completed', 20, False))
        self.service.begin()
        self.assertFalse(self.service.complete('filling.completed', 20))
        self.assertEqual(os.listdir(events.OUTBOX), [])

    def test_net_mass_no_implicit_volume_and_cancelled_zero(self):
        self.service.begin({'batchId': 'batch-1', 'planVersion': 'sha256:old'})
        self.assertTrue(self.service.complete('filling.cancelled', 0))
        payload = json.loads(self.payload())
        self.assertNotIn('volumeL', payload)
        self.assertEqual(payload['weight'], 0)
        self.assertEqual(payload['unit'], 'g')

    def test_capacity_preserves_existing_results(self):
        self.assertTrue(self.service.complete('weighing.completed', 20, True))
        body = self.payload()
        with patch.object(events, 'MAX_PENDING', 1):
            self.assertFalse(self.service.can_record())
            self.service.begin(CONTEXT)
            self.assertFalse(self.service.complete('weighing.completed', 30, True))
        self.assertEqual(self.payload(), body)

    def test_recover_staged_result_after_power_interruption(self):
        self.assertTrue(self.service.complete('weighing.completed', 20, True))
        path = next(Path(events.OUTBOX).glob('*.json'))
        body = path.read_text()
        path.rename(path.with_suffix('.tmp'))
        events.ScaleEvents()
        self.assertEqual(self.payload(), body)

    def test_unknown_clock_blocks_new_results(self):
        events._clock_offset = None
        with patch('api.scale_events.time.gmtime', return_value=(2000,1,1,0,0,0,0,0)):
            self.assertFalse(self.service.complete('weighing.completed', 20, True))
        self.assertEqual(os.listdir(events.OUTBOX), [])


class FlowTests(unittest.TestCase):
    def test_valve_closes_before_result_is_saved(self):
        order = []
        app = object.__new__(KegFillerApp)
        app._selected_keg = {'empty_weight_g': 3000}
        app._filling_stop_weight_g = 23000
        app._read_and_update_weight = lambda screen: 23000
        app._weight = lambda: types.SimpleNamespace(set_ok_visible=lambda value: None)
        app._close_relay = lambda: order.append('closed')
        app._events = types.SimpleNamespace(resume=lambda: order.append('resume'))
        app._save_fill_result = lambda kind: order.append(kind)
        app._tick_filling()
        self.assertEqual(order, ['closed', 'filling.completed', 'resume'])
        self.assertEqual(app._fill_net_g, 20000)
        self.assertEqual(app._state, _STATE_FILLING_DONE_ACK)

    def test_worker_busy_prevents_valve_open(self):
        app = object.__new__(KegFillerApp)
        app._events = types.SimpleNamespace(suspend=lambda: False)
        app._open_relay = lambda: self.fail('valve opened during HTTP request')
        app._start_filling()

    def test_no_flow_closes_valve_without_network(self):
        order = []
        app = object.__new__(KegFillerApp)
        app._fill_reference_weight_g = 5000
        app._fill_reference_at = 0
        app._fill_stall_timeout_s = 10
        app._close_relay = lambda: order.append('closed')
        app._show_filling_stalled = lambda: order.append('stalled')
        with patch('apps.keg_filler_app._ticks_ms', return_value=11000):
            app._check_fill_stalled(5000)
        self.assertEqual(order, ['closed', 'stalled'])

    def test_recipe_keeps_step_until_persisted(self):
        app = object.__new__(RecipeApp)
        screen = types.SimpleNamespace(set_status=lambda text: None)
        app._weight = lambda: screen
        app._read_and_update_weight = lambda screen: 20
        app._target_g = 20
        app._last_in_range = False
        app.hardware = types.SimpleNamespace(button=types.SimpleNamespace(was_short_pressed=lambda: True))
        app._weight_stable = lambda: True
        app.i18n = None
        app._event_context = CONTEXT
        app._events = types.SimpleNamespace(complete=lambda *a, **k: False, error='disk full')
        self.assertFalse(app._weighing_reached_target(1))
        app._events.complete = lambda *a, **k: True
        self.assertTrue(app._weighing_reached_target(1))

    def test_portal_fields_and_bounds(self):
        fields = {row[0] for row in portal_html.FIELDS}
        for key in ('HTTP_API_TOKEN', 'HTTP_API_BASE_URL', 'HTTP_WEBHOOK_URL', 'HTTP_LIVE_ENABLED'):
            self.assertIn(key, fields)
        self.assertFalse(config_registry.validate_payload({'HTTP_MEASUREMENT_INTERVAL_MS': 999})[0])
        self.assertTrue(config_registry.validate_payload({'BREWING_SOFTWARE': 'generic_http'})[0])
        self.assertTrue(config_registry.validate_payload({'BREWING_SOFTWARE': 'brewfather'})[0])

    def test_outbox_is_protected_from_firmware_updates(self):
        for path in ('storage/scale_events/a.json', 'storage/scale_events/a.blocked', 'storage/scale_events/a.tmp'):
            self.assertFalse(include_runtime_path(path))
            with self.assertRaises(RuntimeError):
                _safe_path(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
