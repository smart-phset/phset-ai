"""Provider-neutral contracts and verdict policy, without model dependencies."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import unittest

from detectors import DetectionBox, DetectionResult, Detector
from live_camera import summarize_detections, summarize_result


def box(label, confidence):
    return DetectionBox(label, confidence, (1.25, 2.5, 30.75, 40.0))


class DetectionTypesTests(unittest.TestCase):
    def test_box_normalization_precision_and_immutability(self):
        detection = box("Contaminated", 0.799999999)
        self.assertEqual(detection.label, "contaminated")
        self.assertEqual(detection.confidence, 0.799999999)
        self.assertEqual(detection.xyxy, (1.25, 2.5, 30.75, 40.0))
        with self.assertRaises(FrozenInstanceError):
            detection.label = "healthy"

    def test_result_defaults_are_independent(self):
        first, second = DetectionResult(), DetectionResult()
        first.boxes.append(box("Healthy", 0.9))
        self.assertEqual(second.boxes, [])
        self.assertEqual(
            (second.inference_ms, second.captured_at, second.provider, second.model_id),
            (0.0, None, "", ""),
        )

    def test_result_metadata(self):
        boxes = [box("Healthy", 0.987654321)]
        result = DetectionResult(boxes, 12.345, "2026-10-08T09:00:00Z", "test", "model/1")
        self.assertEqual(result.boxes, boxes)
        self.assertEqual(result.inference_ms, 12.345)
        self.assertEqual(result.captured_at, "2026-10-08T09:00:00Z")
        self.assertEqual((result.provider, result.model_id), ("test", "model/1"))

    def test_detector_requires_detect_and_has_default_close(self):
        with self.assertRaises(TypeError):
            Detector()

        class StubDetector(Detector):
            def detect(self, frame):
                return DetectionResult()

        detector = StubDetector()
        self.assertIsInstance(detector.detect(None), DetectionResult)
        self.assertIsNone(detector.close())


class NormalizedVerdictTests(unittest.TestCase):
    def test_contamination_thresholds_without_rounding(self):
        for confidence, severity in (
            (0.81, "RED"), (0.80, "RED"), (0.799999999, "AMBER"),
            (0.79, "AMBER"), (0.40, "AMBER"), (0.399999999, "GREY"), (0.3, "GREY"),
        ):
            with self.subTest(confidence=confidence):
                summary = summarize_detections([box("Contaminated", confidence)])
                self.assertEqual(summary["severity"], severity)
                self.assertEqual(summary["verdict"], "contamination_suspected")
                self.assertEqual(summary["max_contaminated_conf"], confidence)
                self.assertEqual(summary["boxes"][0]["conf"], confidence)

    def test_healthy_only(self):
        summary = summarize_detections([box("Healthy", 0.9)])
        self.assertEqual((summary["severity"], summary["verdict"]),
                         ("GREEN", "no_contamination_seen"))

    def test_empty_and_unknown_are_grey(self):
        for boxes in ([], [box("Other", 0.99)]):
            with self.subTest(boxes=boxes):
                summary = summarize_detections(boxes)
                self.assertEqual((summary["severity"], summary["verdict"]),
                                 ("GREY", "no_detection"))

    def test_contamination_wins_independent_of_order(self):
        boxes = [box("Healthy", 0.99), box("Contaminated", 0.3)]
        for ordered in (boxes, boxes[::-1]):
            summary = summarize_detections(ordered)
            self.assertEqual(summary["severity"], "GREY")
            self.assertEqual(summary["verdict"], "contamination_suspected")
            self.assertEqual((summary["n_healthy"], summary["n_contaminated"]), (1, 1))
            self.assertEqual(summary["max_conf"], 0.99)
            self.assertEqual(summary["max_contaminated_conf"], 0.3)

    def test_existing_prefix_policy(self):
        summary = summarize_detections([box("Contamination", 0.8), box("Healthy bag", 0.9)])
        self.assertEqual((summary["n_contaminated"], summary["n_healthy"]), (1, 1))
        self.assertEqual(summary["severity"], "RED")

    def test_legacy_adapter_matches_normalized_summary(self):
        tensor = lambda values: SimpleNamespace(tolist=lambda: values)
        boxes = [box("Healthy", 0.99), box("Contaminated", 0.799999999)]
        legacy = SimpleNamespace(
            names={0: "Healthy", 1: "Contaminated"},
            boxes=SimpleNamespace(cls=tensor([0, 1]), conf=tensor([b.confidence for b in boxes]),
                                  xyxy=tensor([list(b.xyxy) for b in boxes])),
        )
        self.assertEqual(summarize_result(legacy), summarize_detections(boxes))
        self.assertEqual(summarize_result(), summarize_detections([]))
        self.assertEqual(summarize_result(SimpleNamespace(boxes=None)), summarize_detections([]))
        self.assertEqual(summarize_result(legacy)["boxes"][0],
                         {"label": "healthy", "conf": 0.99, "xyxy": [1.25, 2.5, 30.75, 40.0]})


if __name__ == "__main__":
    unittest.main()
