"""Local YOLO inference normalized into the shared detector contract."""

from datetime import datetime, timezone
import time

from .base import Detector
from .types import DetectionBox, DetectionResult


class LocalUltralyticsDetector(Detector):
    def __init__(self, weights: str, confidence: float,
                 device: str | None = None, imgsz: int = 416,
                 *, model_factory=None):
        # Lazy import preserves hardware-independent tests and optional providers.
        if model_factory is None:
            from ultralytics import YOLO
            model_factory = YOLO
        self.weights = str(weights)
        self.confidence = confidence
        self.device = device
        self.imgsz = imgsz
        self.model = model_factory(self.weights)

    def detect(self, frame) -> DetectionResult:
        captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        start = time.monotonic()
        options = dict(conf=self.confidence, imgsz=self.imgsz, verbose=False)
        if self.device is not None:
            options["device"] = self.device
        result = self.model.predict(frame, **options)[0]
        boxes = []
        if result.boxes is not None:
            for cls, conf, xyxy in zip(result.boxes.cls.tolist(),
                                      result.boxes.conf.tolist(),
                                      result.boxes.xyxy.tolist()):
                boxes.append(DetectionBox(
                    label=result.names[int(cls)], confidence=float(conf),
                    xyxy=tuple(float(value) for value in xyxy),
                ))
        return DetectionResult(
            boxes=boxes, inference_ms=(time.monotonic() - start) * 1000,
            captured_at=captured_at, provider="local", model_id=self.weights,
        )
