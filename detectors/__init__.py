"""Provider-neutral detector contracts."""

from .base import Detector
from .types import DetectionBox, DetectionResult

__all__ = ["Detector", "DetectionBox", "DetectionResult"]
