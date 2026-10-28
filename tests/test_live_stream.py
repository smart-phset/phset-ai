"""No webcam, model or external services are used in these tests."""
import io
import threading
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import live_camera as live
from live_stream import LatestFrame, mjpeg_part, streaming_server


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.state = LatestFrame("webcam-0")
        self.frame = np.zeros((300, 640, 3), dtype=np.uint8)

    def publish(self):
        self.state.publish(cv2, self.frame)

    def test_jpeg_annotation_no_detection_and_latest_only(self):
        summary = live.summarize_detections([])
        annotated = live.draw_overlay(cv2, self.frame.copy(), summary, 5, 0)
        self.assertTrue(np.any(annotated != self.frame))
        self.state.publish(cv2, annotated)
        self.assertTrue(self.state.jpeg.startswith(b'\xff\xd8'))
        decoded = cv2.imdecode(np.frombuffer(self.state.jpeg, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(decoded.shape, self.frame.shape)
        first = self.state.jpeg
        self.publish()
        self.assertNotEqual(self.state.jpeg, first)
        self.assertEqual(self.state.sequence, 2)
        consumers = [self.state.frames(), self.state.frames()]
        for consumer in consumers:
            self.assertEqual(next(consumer), mjpeg_part(self.state.jpeg))
            consumer.close()
        self.assertFalse(self.state.stopped.is_set())

    def test_slow_viewer_skips_frames_and_disconnect_does_not_stop_peer(self):
        self.publish()
        slow, fast = self.state.frames(), self.state.frames()
        next(slow)
        next(fast)
        for _ in range(12):
            self.publish()
            self.assertEqual(next(fast), mjpeg_part(self.state.jpeg))
        self.assertEqual(next(slow), mjpeg_part(self.state.jpeg))
        slow.close()
        self.publish()
        self.assertEqual(next(fast), mjpeg_part(self.state.jpeg))
        fast.close()
        self.assertTrue(self.state.health()['streaming'])

    def test_new_viewer_never_receives_stale_frame(self):
        self.publish()
        self.state.updated -= 20
        self.assertEqual(list(self.state.frames()), [])

    def test_format_and_health(self):
        self.assertEqual(mjpeg_part(b'jpeg'), b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: 4\r\n\r\njpeg\r\n')
        self.assertEqual(self.state.health(), dict(status='starting', camera='webcam-0', streaming=False))
        self.publish()
        self.assertTrue(self.state.health()['streaming'])
        self.state.updated -= 20
        self.assertEqual(self.state.health()['status'], 'stalled')
        self.state.unavailable()
        self.assertEqual(self.state.health()['status'], 'camera_unavailable')
        self.assertIsNone(self.state.jpeg)

    def test_shutdown_wakes_waiting_consumer(self):
        output = []
        consumer = threading.Thread(target=lambda: output.extend(self.state.frames()))
        consumer.start()
        self.state.close()
        consumer.join(timeout=2)
        self.assertFalse(consumer.is_alive())
        self.assertEqual(output, [])

    def test_encoding_failure(self):
        encoder = MagicMock()
        encoder.imencode.return_value = (False, None)
        with self.assertRaises(RuntimeError):
            self.state.publish(encoder, self.frame)
        self.assertFalse(self.state.health()['streaming'])

    def test_http_disconnect_closes_consumer_without_stopping_producer(self):
        self.publish()
        consumer = self.state.frames()
        with patch('live_stream.ThreadingHTTPServer') as server, patch('live_stream.threading.Thread'):
            streaming_server(self.state)
            handler_type = server.call_args.args[1]
        handler = object.__new__(handler_type)
        handler.path = '/stream.mjpg'
        handler.connection = MagicMock()
        handler.wfile = MagicMock()
        handler.wfile.write.side_effect = BrokenPipeError
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        with patch.object(self.state, 'frames', return_value=consumer):
            handler.do_GET()
        self.assertIsNone(consumer.gi_frame)
        self.assertTrue(handler.close_connection)
        self.assertTrue(self.state.health()['streaming'])
        handler.path = '/health'
        handler.wfile = io.BytesIO()
        handler.do_GET()
        self.assertIn(b'"streaming": true', handler.wfile.getvalue())

    def test_serve_uses_one_capture_exact_inferred_frame_and_publisher(self):
        fake_cv = MagicMock()
        camera = fake_cv.VideoCapture.return_value
        camera.read.return_value = (True, self.frame)
        detector = MagicMock()
        from detectors import DetectionResult
        detector.detect.return_value = DetectionResult([], 5, '2026-10-25T00:00:00Z', 'local', 'test')
        original_publish = self.state.publish
        def publish(cv, frame):
            original_publish(cv2, frame)
            self.state.close()
        with patch.object(live, 'build_detector', return_value=detector), \
                patch.object(live, 'BackendPublisher') as publisher, \
                patch.object(live, 'ThreadPoolExecutor') as pool, \
                patch.object(self.state, 'publish', side_effect=publish):
            live.run_camera(live.parse_args(['--serve', '--backend-url', 'http://localhost:9090']), fake_cv, stream_state=self.state)
        fake_cv.VideoCapture.assert_called_once_with(0)
        detector.detect.assert_called_once_with(self.frame)
        self.assertTrue(self.state.jpeg.startswith(b'\xff\xd8'))
        self.assertEqual(publisher.return_value.offer.call_args.args[1], 'webcam-0')
        self.assertEqual(publisher.return_value.offer.call_args.args[0]['verdict'], 'no_detection')
        publisher.return_value.close.assert_called_once()
        detector.close.assert_called_once()
        camera.release.assert_called_once()
        fake_cv.imshow.assert_not_called()
        pool.assert_not_called()

    def test_serve_cli(self):
        args = live.parse_args(['--serve'])
        self.assertEqual((args.serve, args.host, args.port), (True, '127.0.0.1', 8001))
        with patch('sys.stderr'), self.assertRaises(SystemExit):
            live.parse_args(['--port', '0'])

class RecoveryTests(unittest.TestCase):
    def test_network_capture_timeouts_are_set_at_open(self):
        cv = MagicMock()
        args = live.parse_args(['--serve', '--source', 'http://camera/stream'])
        live.open_video_source(cv, args)
        cv.VideoCapture.assert_called_once_with('http://camera/stream', cv.CAP_FFMPEG, [
            cv.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv.CAP_PROP_READ_TIMEOUT_MSEC, 5000])

    def test_initially_offline_network_camera_reconnects_with_one_detector(self):
        cv = MagicMock()
        camera = cv.VideoCapture.return_value
        camera.isOpened.side_effect = [False, True]
        frame = np.zeros((300, 640, 3), dtype=np.uint8)
        camera.read.side_effect = [(False, None), (True, frame)]
        state = LatestFrame('esp32-cam')
        detector = MagicMock()
        from detectors import DetectionResult
        detector.detect.return_value = DetectionResult([], 5, '2026-10-28T00:00:00Z', 'local', 'test')
        def publish(*_args):
            state.close()
        with patch.object(live, 'build_detector', return_value=detector) as build, \
                patch.object(live, 'BackendPublisher'), \
                patch.object(state, 'publish', side_effect=publish):
            live.run_camera(live.parse_args(['--serve', '--source', 'http://camera/stream', '--reconnect-delay', '0.001']), cv, stream_state=state)
        build.assert_called_once()
        self.assertEqual(cv.VideoCapture.call_count, 2)
        detector.detect.assert_called_once_with(frame)
        detector.close.assert_called_once()
        self.assertEqual(camera.release.call_count, 2)
