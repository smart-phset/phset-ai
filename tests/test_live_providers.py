"""Provider selection and camera scheduling without hardware or hosted calls."""
import builtins
from concurrent.futures import Future
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import live_camera as live
from backend_publisher import detection_payload
from detectors import DetectionBox, DetectionResult
from detectors.roboflow_detector import DetectorUnavailableError


class ProviderTests(unittest.TestCase):
    def test_local_default_and_explicit_no_remote_runtime(self):
        original = builtins.__import__
        def guarded(name, *a, **kw):
            if name.startswith(('inference_sdk', 'detectors.roboflow_detector')):
                raise AssertionError('local imported hosted provider')
            return original(name, *a, **kw)
        for flags in ([], ['--model-provider', 'local']):
            args = live.parse_args(flags)
            self.assertEqual(args.model_provider, 'local')
            with patch('builtins.__import__', side_effect=guarded), \
                    patch.dict('os.environ', {}, clear=True), \
                    patch.object(live, 'LocalUltralyticsDetector') as factory:
                live.build_detector(args)
                factory.assert_called_once_with(live.DEFAULT_WEIGHTS, .4, None, 416, model_factory=None)

    def test_remote_factory_configuration_without_weights(self):
        args = live.parse_args(['--model-provider', 'roboflow', '--weights', '/absent.pt',
                                '--roboflow-model-id', 'custom/2', '--conf', '.63',
                                '--roboflow-api-url', 'http://localhost:9001'])
        with patch.dict('os.environ', {'ROBOFLOW_API_KEY': 'dummy'}), \
                patch('detectors.roboflow_detector.RoboflowDetector') as factory:
            self.assertIs(live.build_detector(args), factory.return_value)
            factory.assert_called_once_with(model_id='custom/2', api_url='http://localhost:9001', confidence=.63)

    def test_missing_key_before_camera_or_sdk(self):
        cv = MagicMock()
        with patch.dict('os.environ', {}, clear=True), \
                patch('detectors.roboflow_detector.RoboflowDetector') as factory:
            with self.assertRaisesRegex(ValueError, 'ROBOFLOW_API_KEY'):
                live.run_camera(live.parse_args(['--model-provider', 'roboflow']), cv)
            factory.assert_not_called()
            cv.VideoCapture.assert_not_called()

    def test_cli_validation_and_local_options(self):
        args = live.parse_args(['--imgsz', '640', '--device', 'cpu', '--conf', '.6'])
        with patch.object(live, 'LocalUltralyticsDetector') as factory:
            live.build_detector(args)
            factory.assert_called_once_with(live.DEFAULT_WEIGHTS, .6, 'cpu', 640, model_factory=None)
        for flags in (['--model-provider', 'bad'], ['--imgsz', '0'],
                      ['--roboflow-api-url', 'https://user:secret@example.com'],
                      ['--roboflow-model-id', '']):
            with patch('sys.stderr'), self.assertRaises(SystemExit):
                live.parse_args(flags)

    def test_payload_equivalence(self):
        payloads = []
        for provider in ('local', 'roboflow'):
            detector = MagicMock()
            detector.detect.return_value = DetectionResult(
                [DetectionBox('Contaminated', .799999999, (1., 2., 3., 4.))],
                12.5, '2026-10-08T00:00:00Z', provider, 'model')
            payload = detection_payload(live.infer_detector(detector, SimpleNamespace(shape=(480,640,3))), 'esp32-cam')
            payload.pop('event_id')
            payloads.append(payload)
        self.assertEqual(payloads[0], payloads[1])
        self.assertEqual(payloads[0]['severity'], 'AMBER')

    def run_loop(self, times, futures, reads=None, keys=None, source=True):
        cv, detector = MagicMock(), MagicMock()
        frame = MagicMock(); frame.shape = (480, 640, 3)
        camera = cv.VideoCapture.return_value
        camera.read.side_effect = reads
        camera.read.return_value = (True, frame)
        cv.waitKey.side_effect = keys if keys is not None else [-1]*(len(times)-1)+[ord('q')]
        args = live.parse_args(['--model-provider','roboflow','--fps','1', '--backend-url','http://localhost:9090'] +
                               (['--source','http://camera/stream'] if source else []))
        with ExitStack() as stack:
            stack.enter_context(patch.object(live, 'build_detector', return_value=detector))
            pool = stack.enter_context(patch.object(live, 'ThreadPoolExecutor'))
            pool.return_value.submit.side_effect = futures
            publisher = stack.enter_context(patch.object(live, 'BackendPublisher')).return_value
            overlay = stack.enter_context(patch.object(live, 'draw_overlay', side_effect=lambda c,f,*a:f))
            stack.enter_context(patch.object(live.time, 'monotonic', side_effect=times))
            stack.enter_context(patch.object(live.time, 'sleep'))
            live.run_camera(args, cv)
        detector.close.assert_called_once()
        publisher.close.assert_called_once()
        cv.destroyAllWindows.assert_called_once()
        pool.assert_called_once_with(max_workers=1)
        pool.return_value.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
        return cv, pool.return_value, overlay, publisher

    def completed(self, error=False):
        f = Future()
        if error:
            f.set_exception(DetectorUnavailableError('private details'))
        else:
            s = live.summarize_detections([DetectionBox('Healthy', .9, (1,2,3,4))])
            s.update(shape=(480,640), ms=10, captured_at='2026-10-08T00:00:00Z')
            f.set_result(s)
        return f

    def test_failure_preview_grey_scheduled_recovery_no_reconnect(self):
        cv, pool, overlay, publisher = self.run_loop(
            [0, .1, .2, 1, 1.1], [self.completed(True), self.completed()])
        self.assertEqual(cv.imshow.call_count, 5)
        cv.VideoCapture.assert_called_once_with('http://camera/stream')
        self.assertEqual(pool.submit.call_count, 2)
        self.assertEqual([c.args[2]['severity'] for c in overlay.call_args_list], ['GREY']*4+['GREEN'])
        self.assertEqual([c.args[0]['severity'] for c in publisher.offer.call_args_list], ['GREY','GREEN'])
        cv.VideoCapture.return_value.set.assert_called_once_with(cv.CAP_PROP_BUFFERSIZE, 1)

    def test_single_inflight_drops_frames_preview_continues(self):
        cv, pool, _, _ = self.run_loop([0,1,2,3], [Future()])
        pool.submit.assert_called_once()
        self.assertEqual(cv.imshow.call_count, 4)
        self.assertIs(pool.submit.call_args.args[0], live.infer_detector)

    def test_stale_success_expires_and_slow_result_never_green(self):
        _, _, overlay, publisher = self.run_loop([0,.1,1,6], [self.completed(), Future()])
        self.assertEqual([c.args[2]['severity'] for c in overlay.call_args_list], ['GREY','GREEN','GREEN','GREY'])
        self.assertEqual(publisher.offer.call_args_list[-1].args[0]['message'], 'Could not inspect')
        _, _, overlay, _ = self.run_loop([0,6], [self.completed(), Future()])
        self.assertTrue(all(c.args[2]['severity']=='GREY' for c in overlay.call_args_list))

    def test_actual_camera_failure_reconnects(self):
        cv, _, _, _ = self.run_loop([0,1], [Future()],
                                   reads=[(False,None),(True,MagicMock()),(True,MagicMock())])
        self.assertEqual(cv.VideoCapture.call_count, 2)
        self.assertEqual(cv.VideoCapture.return_value.release.call_count, 2)

    def test_ctrl_c_cleanup(self):
        cv, _, _, _ = self.run_loop([0], [Future()], keys=[KeyboardInterrupt()])
        cv.VideoCapture.return_value.release.assert_called_once()


if __name__ == '__main__':
    unittest.main()
