"""Evaluation scoring and CLI integration; no live inference or network."""
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from detectors import DetectionBox, DetectionResult
from tools import evaluate_detector as ev


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.block = patch('socket.socket.connect', side_effect=AssertionError('network forbidden'))
        self.block.start(); self.addCleanup(self.block.stop)
        self.frame = np.zeros((8,8,3), dtype=np.uint8)

    def row(self, expected, boxes=(), latency=10):
        detector = MagicMock()
        detector.detect.return_value = DetectionResult(list(boxes), latency, provider='local', model_id='test')
        return ev.evaluate([(Path('image.png'), expected)], detector, 'local', lambda _:self.frame)[0]

    def box(self, label, confidence=.9):
        return DetectionBox(label, confidence, (0.,0.,4.,4.))

    def test_healthy(self):
        r=self.row('healthy',[self.box('Healthy')]); self.assertTrue(r['correct']); self.assertEqual(r['severity'],'GREEN')

    def test_contaminated(self):
        for conf in (.4,.79,.8):
            self.assertTrue(self.row('contaminated',[self.box('Contaminated',conf)])['correct'])

    def test_contamination_miss(self):
        r=self.row('contaminated',[self.box('Healthy')]); self.assertFalse(r['correct']); self.assertEqual(r['outcome'],'contamination_miss')

    def test_low_confidence_miss_distinct(self):
        r=self.row('contaminated',[self.box('Contaminated',.39999),self.box('Healthy')])
        self.assertEqual(r['outcome'],'low_confidence_contamination_miss'); self.assertFalse(r['correct'])
        a=ev.aggregate([r]); self.assertEqual(a['contamination_misses'],1); self.assertEqual(a['low_confidence_contamination_misses'],1)

    def test_healthy_false_alert(self):
        r=self.row('healthy',[self.box('Contaminated')]); self.assertEqual(ev.aggregate([r])['healthy_false_alerts'],1)

    def test_negative_no_detection(self):
        self.assertTrue(self.row('negative')['correct'])
        self.assertEqual(ev.aggregate([self.row('negative')])['no_detection_count'],1)

    def test_negative_green_false_claim(self):
        r=self.row('negative',[self.box('Healthy')]); self.assertFalse(r['correct'])
        self.assertEqual(ev.aggregate([r])['negative_scene_false_claims'],1)

    def test_negative_contamination_false_alert(self):
        r=self.row('negative',[self.box('Contaminated',.3)])
        self.assertFalse(r['correct']); self.assertEqual(ev.aggregate([r])['negative_contamination_false_alerts'],1)

    def test_unknown_not_green(self):
        self.assertFalse(self.row('healthy',[self.box('unknown')])['correct'])

    def test_provider_unavailable_continues_safe(self):
        d=MagicMock();d.detect.side_effect=[RuntimeError('secret'),DetectionResult()]
        rows=ev.evaluate([(Path('a.png'),'healthy'),(Path('b.png'),'negative')],d,'roboflow',lambda _:self.frame)
        self.assertEqual(rows[0]['error'],'provider_unavailable');self.assertEqual(rows[0]['severity'],'GREY')
        self.assertNotIn('secret',str(rows));self.assertTrue(rows[1]['correct'])
        self.assertEqual(ev.aggregate(rows)['unavailable_error'],1)

    def test_unreadable_image(self):
        for loader in (lambda _:None,lambda _:np.array([]),MagicMock(side_effect=OSError('bad'))):
            d=MagicMock();r=ev.evaluate([(Path('a.jpg'),'healthy')],d,'local',loader)[0]
            self.assertEqual(r['error'],'unreadable_image');d.detect.assert_not_called()

    def test_malformed_output_safe(self):
        for result in (None,DetectionResult([self.box('Healthy'),self.box('Contaminated',float('nan'))]),
                       DetectionResult(inference_ms=float('inf'))):
            d=MagicMock(); d.detect.return_value=result
            r=ev.evaluate([(Path('x.png'),'healthy')],d,'local',lambda _:self.frame)[0]
            self.assertEqual((r['error'],r['severity']),('malformed_result','GREY'))

    def test_discovery_deterministic_excludes_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ev.CATEGORIES:(root/name).mkdir()
            for name in ('healthy/z.JPG','healthy/a.png','negative/b.webp','negative/results.csv'):
                (root/name).touch()
            files=ev.discover_images(root)
            self.assertEqual([p.relative_to(root).as_posix() for p,_ in files],['healthy/a.png','healthy/z.JPG','negative/b.webp'])
            self.assertEqual(files,ev.discover_images(root))

    def test_bad_dataset_and_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):ev.discover_images(tmp)
        a=ev.aggregate([]);self.assertIsNone(a['accuracy']);self.assertIsNone(a['p95_inference_ms'])

    def test_latency_mean_p95(self):
        rows=[self.row('negative',latency=i) for i in range(1,21)]
        a=ev.aggregate(rows);self.assertEqual(a['average_inference_ms'],10.5);self.assertEqual(a['p95_inference_ms'],19)
        self.assertEqual(ev.aggregate(rows[:1])['p95_inference_ms'],1)

    def test_csv_schema_precision(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'results.csv';ev.write_csv(output,[self.row('contaminated',[self.box('Contaminated',.799999999)])])
            with output.open(newline='') as f:
                reader=csv.DictReader(f);self.assertEqual(tuple(reader.fieldnames),ev.FIELDS)
                self.assertEqual(next(reader)['max_conf'],'0.799999999')

    def test_cli_local_selection_and_real_image_decode(self):
        import cv2
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ev.CATEGORIES:(root/name).mkdir()
            cv2.imwrite(str(root/'healthy'/'fixture.png'),self.frame)
            with patch('live_camera.LocalUltralyticsDetector') as factory,patch('builtins.print'):
                factory.return_value.detect.return_value=DetectionResult([self.box('Healthy')])
                ev.main(['--dataset',tmp,'--output',str(root/'results.csv')])
                factory.assert_called_once();factory.return_value.detect.assert_called_once();factory.return_value.close.assert_called_once()
                with (root/'results.csv').open() as f:self.assertEqual(next(csv.DictReader(f))['correct'],'True')

    def test_remote_selection_no_http(self):
        args=ev.parse_args(['--dataset','evaluation','--output','out.csv','--model-provider','roboflow'])
        with patch.dict('os.environ',{'ROBOFLOW_API_KEY':'dummy'}),patch('detectors.roboflow_detector.RoboflowDetector') as factory:
            ev.build_detector(args);factory.assert_called_once_with(model_id='contamination-detection-ozkwx/1',api_url='https://serverless.roboflow.com',confidence=.4)

    def test_empty_cli_no_detector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ev.CATEGORIES:(root/name).mkdir()
            with patch.object(ev,'build_detector') as factory,patch('builtins.print'):
                ev.main(['--dataset',tmp,'--output',str(root/'empty.csv')]);factory.assert_not_called()


if __name__ == '__main__':unittest.main()
