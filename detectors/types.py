"""Detection data shared by all model providers."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DetectionBox:
    """One box in original-frame pixels, with unrounded confidence."""

    label: str
    confidence: float
    xyxy: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", self.label.lower())


@dataclass
class DetectionResult:
    boxes: list[DetectionBox] = field(default_factory=list)
    inference_ms: float = 0.0
    captured_at: str | None = None
    provider: str = ""
    model_id: str = ""
