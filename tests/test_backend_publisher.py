"""Hardware-independent publisher regression tests."""
from datetime import datetime
import json
import threading
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from uuid import UUID
from backend_publisher import BackendPublisher, detection_payload
import live_camera


def summary(severity='GREEN', verdict='no_contamination_seen'):
    return dict(verdict=verdict, severity=severity, message='test', n_contaminated=0,
                n_healthy=1, max_conf=.95, max_contaminated_conf=0., shape=(720,1280),
                ms=83.7, boxes=[dict(label='healthy',conf=.95,xyxy=[1.2,2,30,40])])


class PublisherTests(unittest.TestCase):
    def test_payload(self):
        p=detection_payload(summary(),'webcam-0')
        self.assertEqual(UUID(p['event_id']).version,4)
        self.assertEqual(datetime.fromisoformat(p['captured_at']).utcoffset().total_seconds(),0)
        self.assertTrue(p['captured_at'].endswith('Z'))
        self.assertEqual((p['width'],p['height'],p['inference_ms']),(1280,720,84))
        self.assertEqual(p['boxes'][0]['xyxy'],[1,2,30,40])
        self.assertEqual(set(p),{'event_id','camera_id','captured_at','verdict','severity','message',
                                'n_contaminated','n_healthy','max_conf','max_contaminated_conf',
                                'width','height','inference_ms','boxes'})
        self.assertNotEqual(p['event_id'],detection_payload(summary(),'webcam-0')['event_id'])
        s=summary(); s['captured_at']='2026-10-06T11:25:00Z'
        self.assertEqual(detection_payload(s,'webcam-0')['captured_at'],s['captured_at'])

    def test_disabled(self):
        p=BackendPublisher()
        self.assertFalse(p.offer({},'webcam-0'))
        self.assertIsNone(p.worker)
        p.close()

    def test_periodic_change_and_no_spam(self):
        with patch('backend_publisher.threading.Thread'):
            p=BackendPublisher('http://localhost:9090')
            self.assertTrue(p.offer(summary(),'webcam-0',0))
            for t in (.1,.2,1,4.99):
                self.assertFalse(p.offer(summary(),'webcam-0',t))
            self.assertTrue(p.offer(summary(),'webcam-0',5))
            self.assertTrue(p.offer(summary('AMBER','contamination_suspected'),'webcam-0',5.1))
            self.assertTrue(p.offer(summary('RED','contamination_suspected'),'webcam-0',5.2))
            self.assertFalse(p.offer(summary('RED','contamination_suspected'),'webcam-0',5.3))
            p.close()
            self.assertFalse(p.offer(summary(),'webcam-0',20))

    def test_headers_timeout_and_network_failure(self):
        opener=MagicMock()
        opener.return_value.__enter__.return_value.status=201
        with patch('backend_publisher.threading.Thread'):
            p=BackendPublisher('http://localhost:9090/',ingest_key='test-key',opener=opener)
            p._send(detection_payload(summary(),'webcam-0'))
            request=opener.call_args.args[0]
            self.assertEqual(request.full_url,'http://localhost:9090/api/ai/detections')
            self.assertEqual(request.get_header('Content-type'),'application/json')
            self.assertEqual(request.get_header('X-smartphset-ai-key'),'test-key')
            self.assertEqual(opener.call_args.kwargs['timeout'],3)
            self.assertEqual(json.loads(request.data)['camera_id'],'webcam-0')
            for failure in (URLError('connection refused'), TimeoutError('slow'),
                            *(HTTPError(p.url, code, 'backend error', {}, None) for code in (401, 403, 500))):
                opener.side_effect=failure
                with self.assertLogs('backend_publisher',level='WARNING'):
                    p._send(detection_payload(summary(),'webcam-0'))
            p.close()

    def test_slow_worker_is_bounded_and_close_does_not_wait(self):
        entered,release=threading.Event(),threading.Event()
        sent=[]
        def send(payload):
            sent.append(payload); entered.set(); release.wait(2)
        with patch.object(BackendPublisher,'_send',side_effect=send):
            p=BackendPublisher('http://localhost:9090',publish_every=.01)
            try:
                p.offer(summary(),'webcam-0',0)
                self.assertTrue(entered.wait(1))
                for i in range(1,100): p.offer(summary(),'webcam-0',i)
                self.assertEqual(len(sent),1)
                self.assertIsInstance(p.pending,dict)
                p.close()
                self.assertIsNone(p.pending)
                self.assertTrue(p.worker.is_alive())
            finally:
                release.set(); p.worker.join(2)
            self.assertEqual(len(sent),1)
            self.assertFalse(p.worker.is_alive())

    def test_latest_pending_is_delivered_after_slow_request(self):
        entered, release, delivered = threading.Event(), threading.Event(), threading.Event()
        sent = []
        def send(payload):
            sent.append(payload)
            if len(sent) == 1:
                entered.set()
                release.wait(2)
            else:
                delivered.set()
        with patch.object(BackendPublisher, '_send', side_effect=send):
            p = BackendPublisher('http://localhost:9090')
            try:
                p.offer(summary(), 'webcam-0', 0)
                self.assertTrue(entered.wait(1))
                for t in range(5, 100, 5):
                    p.offer(summary(), 'webcam-0', t)
                latest = p.pending['event_id']
                release.set()
                self.assertTrue(delivered.wait(1))
                self.assertEqual(len(sent), 2)
                self.assertEqual(sent[1]['event_id'], latest)
            finally:
                release.set()
                p.close()
                p.worker.join(2)

    def test_worker_survives_failure(self):
        called=threading.Event()
        def fail(*args,**kwargs):
            called.set(); raise URLError('offline')
        p=BackendPublisher('http://localhost:9090',opener=fail)
        try:
            with self.assertLogs('backend_publisher',level='WARNING'):
                p.offer(summary(),'webcam-0',0)
                self.assertTrue(called.wait(1))
                p.close(); p.worker.join(1)
        finally: p.close()

    def test_env_and_invalid_arguments(self):
        with patch.dict('os.environ',{'SMARTPHSET_BACKEND_URL':'http://localhost:9090'}):
            self.assertEqual(live_camera.parse_args([]).backend_url,'http://localhost:9090')
        for args in (['--publish-every','0'],['--publish-every','nan'],['--backend-url','file:///x']):
            with self.assertRaises(SystemExit),patch('sys.stderr'): live_camera.parse_args(args)

    def test_camera_quits_with_publisher(self):
        cv,model=MagicMock(),MagicMock()
        cv.VideoCapture.return_value.read.return_value=(True,MagicMock())
        cv.waitKey.return_value=ord('q')
        with patch.object(live_camera,'draw_overlay',side_effect=lambda cv,frame,*a:frame), \
             patch.object(live_camera,'ThreadPoolExecutor'), \
             patch.object(live_camera,'BackendPublisher') as publisher, \
             patch.dict('os.environ', {'SMARTPHSET_AI_INGEST_KEY': 'test-key'}):
            live_camera.run_camera(live_camera.parse_args(['--backend-url','http://localhost:9090']),cv,model)
            publisher.assert_called_once_with('http://localhost:9090', 5, 'test-key')
            publisher.return_value.close.assert_called_once()
        cv.VideoCapture.return_value.release.assert_called_once()
        cv.destroyAllWindows.assert_called_once()
