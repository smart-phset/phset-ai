"""Local provider tests with no real weights, Ultralytics import, or inference."""

from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from detectors import DetectionResult, Detector
from detectors.local_ultralytics import LocalUltralyticsDetector
from live_camera import infer_detector, summarize_detections


def prediction(labels=("Healthy", "Contaminated"), confidences=(0.99, 0.799999999)):
    tensor = lambda values: SimpleNamespace(tolist=lambda: values)
    return SimpleNamespace(names=dict(enumerate(labels)), boxes=SimpleNamespace(
        cls=tensor(list(range(len(labels)))), conf=tensor(list(confidences)),
        xyxy=tensor([[1.125, 2.25, 300.5, 400.75] for _ in labels])))


class LocalDetectorTests(unittest.TestCase):
    def make_detector(self, **kwargs):
        factory = MagicMock()
        factory.return_value.predict.return_value = [prediction()]
        detector = LocalUltralyticsDetector("models/best.pt", 0.4,
                                            model_factory=factory, **kwargs)
        return detector, factory

    def test_load_once_and_default_prediction_options(self):
        detector, factory = self.make_detector()
        frame = object()
        detector.detect(frame)
        detector.detect(frame)
        factory.assert_called_once_with("models/best.pt")
        self.assertEqual(factory.return_value.predict.call_count, 2)
        factory.return_value.predict.assert_called_with(frame, conf=0.4, imgsz=416, verbose=False)
        self.assertIsInstance(detector, Detector)

    def test_custom_options_and_optional_device(self):
        for device in ("cpu", "0", None):
            with self.subTest(device=device):
                factory = MagicMock()
                factory.return_value.predict.return_value = [prediction()]
                detector = LocalUltralyticsDetector("custom.pt", 0.123456789, device, 640,
                                                    model_factory=factory)
                detector.detect("frame")
                options = dict(conf=0.123456789, imgsz=640, verbose=False)
                if device is not None:
                    options["device"] = device
                factory.return_value.predict.assert_called_once_with("frame", **options)

    def test_normalized_boxes_and_metadata(self):
        detector, _ = self.make_detector()
        with patch("detectors.local_ultralytics.time.monotonic", side_effect=[10, 10.125]):
            result = detector.detect(object())
        self.assertIsInstance(result, DetectionResult)
        self.assertEqual([b.label for b in result.boxes], ["healthy", "contaminated"])
        self.assertEqual(result.boxes[1].confidence, 0.799999999)
        self.assertEqual(result.boxes[1].xyxy, (1.125, 2.25, 300.5, 400.75))
        self.assertEqual(result.inference_ms, 125.0)
        self.assertEqual((result.provider, result.model_id), ("local", "models/best.pt"))
        self.assertTrue(result.captured_at.endswith("Z"))
        self.assertEqual(datetime.fromisoformat(result.captured_at).utcoffset().total_seconds(), 0)
        self.assertEqual(summarize_detections(result.boxes)["severity"], "AMBER")

    def test_empty_and_absent_boxes(self):
        detector, factory = self.make_detector()
        for result in (prediction((), ()), SimpleNamespace(boxes=None)):
            factory.return_value.predict.return_value = [result]
            self.assertEqual(detector.detect(object()).boxes, [])

    def test_inference_summary_preserves_backend_contract(self):
        detector, _ = self.make_detector()
        frame = SimpleNamespace(shape=(480, 640, 3))
        summary = infer_detector(detector, frame)
        self.assertEqual(set(summary), {
            "verdict", "message", "severity", "n_contaminated", "n_healthy",
            "max_conf", "max_contaminated_conf", "boxes", "ms", "shape", "captured_at",
        })
        self.assertEqual(summary["shape"], (480, 640))
        self.assertEqual(summary["boxes"][1]["conf"], 0.799999999)
        self.assertEqual(summary["boxes"][1]["xyxy"], [1.125, 2.25, 300.5, 400.75])

    def test_prediction_failure_propagates_without_reload(self):
        detector, factory = self.make_detector()
        factory.return_value.predict.side_effect = RuntimeError("inference failed")
        with self.assertRaisesRegex(RuntimeError, "inference failed"):
            detector.detect(object())
        factory.assert_called_once()


if __name__ == "__main__":
    unittest.main()
