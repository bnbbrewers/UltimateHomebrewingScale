"""Exercise real portal response assembly with short writes/backpressure."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webportal import setup_portal_service as portal, recovery, portal_html
from storage.config_registry import EDITABLE_KEYS


class SlowSocket:
    def __init__(self, limit=17, stalls=True):
        self.limit = limit
        self.stalls = stalls
        self.output = bytearray()
        self.calls = 0
        self.closed = False
    def write(self, data):
        self.calls += 1
        if self.stalls and self.calls % 3 == 0:
            raise OSError(11)
        count = min(len(data), self.limit)
        self.output.extend(data[:count])
        return count
    def close(self):
        self.closed = True


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.service = portal.SetupPortalService()
        self.now = 0
        self.clock = patch.object(portal, '_ticks_ms', side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def transmit(self, body, content_type='text/html; charset=utf-8', socket=None, step_ms=10):
        socket = socket or SlowSocket()
        self.service._client = socket
        self.service._send(socket, 200, content_type, body)
        self.service._client_state = 'write'
        self.service._client_deadline = self.now + portal.CLIENT_TIMEOUT_MS
        for _ in range(10000):
            if self.service._client_state != 'write':
                break
            self.service._progress_write()
            self.now += step_ms
        self.assertEqual(self.service._client_state, 'drain', self.service._last_transfer)
        raw=bytes(socket.output)
        head, received=raw.split(b'\r\n\r\n',1)
        header_length=int(next(line.split(b':',1)[1] for line in head.split(b'\r\n') if line.startswith(b'Content-Length:')))
        expected=(''.join(body) if isinstance(body,list) else body).encode()
        self.assertEqual(header_length,len(expected))
        self.assertEqual(received,expected)
        self.assertEqual(self.service._last_transfer['sentBytes'],len(raw))
        self.assertEqual(self.service._last_transfer['state'],'complete')
        return socket

    def test_recovery_body_not_just_headers(self):
        socket=self.transmit(recovery.page())
        self.assertIn(b'UHS recovery setup',socket.output)
        self.assertIn(b'</html>',socket.output)

    def test_slow_transfer_can_exceed_five_seconds_while_making_progress(self):
        self.transmit(recovery.page(),step_ms=400)
        self.assertGreater(self.now,5000)

    def test_full_settings_survive_short_writes_and_eagain(self):
        values={key:spec['default'] for key,spec in EDITABLE_KEYS.items()}
        self.transmit(portal_html.render_form_parts(values),socket=SlowSocket(limit=11))

    def test_unicode_content_length_and_empty_parts(self):
        self.transmit(['', 'Größe ☕ ', '', '🍺'*200, '', 'fertig'])

    def test_one_write_per_runtime_tick(self):
        socket=SlowSocket(limit=256,stalls=False)
        self.service._client=socket
        self.service._send(socket,200,body=['long '*200])
        self.service._client_deadline=5000
        self.service._progress_write()
        self.assertEqual(socket.calls,1)

    def test_encoded_chunks_are_bounded(self):
        self.service._response_parts=['🍺'*200]
        chunks=[]
        while self.service._response_parts:
            chunks.append(self.service._next_response_chunk())
        self.assertEqual(b''.join(chunks),('🍺'*200).encode())
        self.assertLessEqual(max(map(len,chunks)),portal.WRITE_CHUNK_SIZE)

    def test_health_remains_small_and_complete(self):
        self.transmit('{"ok":true}',content_type='application/json')

    def test_second_response_starts_from_first_body_byte(self):
        self.transmit(recovery.page())
        self.service._close_client()
        self.transmit(['second ', 'response'])

    def test_permanent_backpressure_times_out(self):
        class Blocked(SlowSocket):
            def write(self,data): return None
        socket=Blocked()
        self.service._client=socket
        self.service._send(socket,200,body=['never sent'])
        self.service._client_deadline=5000
        self.now=5001
        self.service._progress_write()
        self.assertTrue(socket.closed)
        self.assertEqual(self.service._last_transfer['state'],'write_timeout')


if __name__=='__main__':
    unittest.main(verbosity=2)
