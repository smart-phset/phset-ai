"""Synchronous inference contract called by the single inference worker."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .types import DetectionResult

if TYPE_CHECKING:
    import numpy as np


class Detector(ABC):
    @abstractmethod
    def detect(self, frame: np.ndarray) -> DetectionResult:
        """Inspect one BGR OpenCV frame; do not call concurrently."""
        raise NotImplementedError

    def close(self) -> None:
        """Release provider resources, if any."""
