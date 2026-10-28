import json
import io
from unittest.mock import patch
import threading
import time
import unittest
from types import SimpleNamespace
import sys

from session_service import Sessions, ServiceError, server, jpeg_size
from detectors.types import DetectionResult


class Detector:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        self.entered.set()
        self.release.wait(2)
        return DetectionResult(boxes=[], inference_ms=1, captured_at='2026-10-28T00:00:00Z', provider='local', model_id='test')


class Frame:
    shape = (480, 640, 3)


class SessionTests(unittest.TestCase):
    def test_isolation_limits_expiry_and_no_user_urls(self):
        m = Sessions(None, limit=2, ttl=.01)
        a = m.create('a', 'browser')
        b = m.create('b', 'browser')
        m.get('a', a)['ai'] = True
        self.assertFalse(m.get('b', b)['ai'])
        self.assertNotEqual(m.snapshot('a', a)['source_id'], m.snapshot('b', b)['source_id'])
        with self.assertRaises(ServiceError) as e:
            m.get('a', b)
        self.assertEqual(e.exception.status, 404)
        with self.assertRaises(ServiceError):
            m.create('a', 'http://internal')
        with self.assertRaises(ServiceError):
            m.create('c', 'browser')
        time.sleep(.02)
        m.expire()
        self.assertFalse(m.sessions)

    def test_simultaneous_inference_is_bounded_and_model_reused(self):
        detector = Detector()
        m = Sessions(detector)
        a, b = m.create('a', 'browser'), m.create('b', 'browser')
        first = threading.Thread(target=lambda: m.detect(Frame()))
        first.start()
        self.assertTrue(detector.entered.wait(1))
        with self.assertRaises(ServiceError) as e:
            m.detect(Frame())
        self.assertEqual(e.exception.status, 429)
        detector.release.set()
        first.join()
        m.detect(Frame())
        self.assertEqual(detector.calls, 2)
        self.assertNotEqual(a, b)

    def test_shared_capture_is_reused_and_last_viewer_releases_it(self):
        class Encoded:
            def tobytes(self):
                return b'jpeg'
        class CV:
            IMWRITE_JPEG_QUALITY = 1
            def imencode(self, *args):
                return True, Encoded()
        class Capture:
            released = False
            def read(self):
                return True, Frame()
            def release(self):
                self.released = True
        capture = Capture()
        m = Sessions(None, {'esp32-cam': 'http://operator-configured'}, cv2=CV())
        with patch('session_service.open_video_source', return_value=(capture, 'esp32-cam')) as opened:
            a = m.create('a', 'esp32-cam')
            b = m.create('b', 'esp32-cam')
            worker = m.workers['esp32-cam']
            deadline = time.monotonic() + 1
            while not worker.state.health()['streaming'] and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(worker.state.health()['streaming'])
            self.assertEqual(opened.call_count, 1)
            with m.lock:
                del m.sessions[a]
                m.expire()
                self.assertFalse(worker.state.stopped.is_set())
                del m.sessions[b]
                m.expire()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertTrue(capture.released)

    def test_multiple_shared_sources_infer_once_per_source_and_publish_correct_ids(self):
        class Encoded:
            def tobytes(self):
                return b'jpeg'
        class CV:
            IMWRITE_JPEG_QUALITY = 1
            def imencode(self, *args):
                return True, Encoded()
        class Capture:
            def read(self):
                return True, Frame()
            def release(self):
                pass
        detector = Detector()
        detector.release.set()
        m = Sessions(detector, {'room-a': 0, 'room-b': 1}, cv2=CV())
        with patch('session_service.open_video_source', side_effect=lambda *_: (Capture(), 'unused')) as opened, patch('session_service.draw_overlay'), patch('session_service.BackendPublisher') as publisher:
            try:
                a = m.create('a', 'room-a')
                peer = m.create('b', 'room-a')
                b = m.create('c', 'room-b')
                with m.lock:
                    for session in m.sessions.values():
                        session['ai'] = True
                        session['revision'] = 1
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    with m.lock:
                        if all(session['result'] for session in m.sessions.values()):
                            break
                    time.sleep(.01)
                self.assertIsNotNone(m.snapshot('a', a)['detection'])
                self.assertIs(m.get('a', a)['result'], m.get('b', peer)['result'])
                self.assertEqual(m.snapshot('c', b)['source_id'], 'room-b')
                self.assertEqual(opened.call_count, 2)
                self.assertEqual({call.args[1] for call in publisher.return_value.offer.call_args_list}, {'room-a', 'room-b'})
            finally:
                workers = list(m.workers.values())
                with m.lock:
                    m.sessions.clear()
                    m.expire()
                for worker in workers:
                    worker.join(1)

    def test_dimensions_checked_before_decode(self):
        import struct
        good = b'\xff\xd8\xff\xc0' + struct.pack('>H B H H B', 8, 8, 480, 640, 0)
        self.assertEqual(jpeg_size(good), (640, 480))
        for data in (b'bad', good[:8], good[:7] + b'\xff\xff' + good[9:]):
            with self.assertRaises(ServiceError):
                jpeg_size(data)

    def test_authenticated_http_session_lifecycle_and_stale_commands(self):
        detector = Detector()
        detector.release.set()
        m = Sessions(detector, cv2=SimpleNamespace(IMREAD_COLOR=1, imdecode=lambda *_: Frame()))
        with patch('session_service.ThreadingHTTPServer.__init__', lambda self, address, handler: setattr(self, 'RequestHandlerClass', handler)):
            http = server(m, 'test-secret', port=0)
        class Socket:
            def __init__(self, raw):
                self.input = io.BytesIO(raw)
                self.output = io.BytesIO()
            def makefile(self, *args):
                return self.input
            def sendall(self, data):
                self.output.write(data)
            def settimeout(self, value):
                pass
        def call(path, method='GET', data=None, owner='a' * 64, key='test-secret', revision=1):
            body = data if isinstance(data, bytes) else json.dumps(data).encode() if data is not None else b''
            raw = (f'{method} {path} HTTP/1.0\r\nAuthorization: Bearer {key}\r\nX-Camera-Owner: {owner}\r\nContent-Type: image/jpeg\r\nX-Camera-Revision: {revision}\r\nContent-Length: {len(body)}\r\n\r\n').encode() + body
            sock = Socket(raw)
            http.RequestHandlerClass(sock, ('127.0.0.1', 1), http)
            head, payload = sock.output.getvalue().split(b'\r\n\r\n', 1)
            return int(head.split()[1]), json.loads(payload)
        self.assertEqual(call('/sessions', 'POST', {'source_id': 'browser'}, key='wrong')[0], 401)
        status, value = call('/sessions', 'POST', {'source_id': 'browser'})
        self.assertEqual(status, 201)
        path = '/sessions/' + value['session_id']
        self.assertEqual(call(path, owner='b' * 64)[0], 404)
        self.assertTrue(call(path + '/start', 'POST', {'revision': 1})[1]['analyzing'])
        import struct
        jpeg = b'\xff\xd8\xff\xc0' + struct.pack('>H B H H B', 8, 8, 480, 640, 0)
        with patch.dict(sys.modules, {'numpy': SimpleNamespace(uint8=1, frombuffer=lambda *args, **kwargs: b'decoded')}):
            status, frame = call(path + '/frames', 'POST', jpeg)
        self.assertEqual(status, 200)
        self.assertEqual(frame['source_id'], value['source_id'])
        self.assertEqual(frame['detection']['shape'], [480, 640])
        self.assertEqual(frame['detection']['severity'], 'GREY')
        self.assertFalse(call(path + '/stop', 'POST', {'revision': 3})[1]['analyzing'])
        self.assertFalse(call(path + '/start', 'POST', {'revision': 2})[1]['analyzing'])
        self.assertEqual(call(path + '/frames', 'POST', {})[0], 409)
        self.assertTrue(call(path + '/start', 'POST', {'revision': 4})[1]['analyzing'])
        self.assertEqual(call(path + '/frames', 'POST', jpeg, revision=1)[0], 409)
        self.assertEqual(call('/sessions', 'DELETE')[0], 200)
        self.assertEqual(call(path)[0], 404)
        _, value = call('/sessions', 'POST', {'source_id': 'browser'})
        path = '/sessions/' + value['session_id']
        self.assertEqual(call(path, 'DELETE')[0], 200)
        self.assertEqual(call(path)[0], 404)

