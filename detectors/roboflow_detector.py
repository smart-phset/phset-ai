"""Roboflow hosted inference using the official SDK and in-memory frames."""

import asyncio
from datetime import datetime, timezone
import math
import os
from time import monotonic

from .base import Detector
from .types import DetectionBox, DetectionResult

DEFAULT_MODEL_ID = "contamination-detection-ozkwx/1"
DEFAULT_API_URL = "https://serverless.roboflow.com"


class DetectorUnavailableError(RuntimeError):
    """No trustworthy result is available from the model service."""


class RoboflowDetector(Detector):
    def __init__(self, model_id: str = DEFAULT_MODEL_ID,
                 api_key: str | None = None, confidence: float = 0.4,
                 api_url: str = DEFAULT_API_URL, timeout: float = 8.0):
        key = os.environ.get("ROBOFLOW_API_KEY", "") if api_key is None else api_key
        if not key or not key.strip():
            raise ValueError("ROBOFLOW_API_KEY is required")
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be finite and between 0 and 1")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and greater than zero")

        # Optional SDK: importing this module does not load remote dependencies.
        from aiohttp import ClientError
        from inference_sdk import InferenceConfiguration, InferenceHTTPClient
        from inference_sdk.http.errors import HTTPClientError
        from requests.exceptions import RequestException

        self._remote_errors = (HTTPClientError, ClientError, RequestException,
                               OSError, TimeoutError)
        self.model_id = model_id
        self.timeout = timeout
        self.client = InferenceHTTPClient(api_url=api_url, api_key=key).configure(
            InferenceConfiguration(
                api_key_transport="header", confidence_threshold=confidence,
                client_downsizing_disabled=True,
            )
        )

    async def _infer(self, frame):
        # SDK 1.7.3 has no synchronous request-timeout option. Its supported
        # async path owns an aiohttp session whose context closes on cancellation.
        # The deadline also bounds the SDK's internal retry/backoff period.
        return await asyncio.wait_for(
            self.client.infer_async(frame, model_id=self.model_id),
            timeout=self.timeout,
        )

    def detect(self, frame) -> DetectionResult:
        """Called synchronously by the sole worker, outside an event loop."""
        captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        start = monotonic()
        try:
            response = asyncio.run(self._infer(frame))
        except self._remote_errors:
            # Never expose SDK exception text, request URLs, or response bodies:
            # any of them may contain a credential. Suppress chained tracebacks.
            raise DetectorUnavailableError("Roboflow inference unavailable") from None
        except (ValueError, TypeError, KeyError):
            raise DetectorUnavailableError("Roboflow returned an invalid detection response") from None
        try:
            boxes = normalize_response(response)
        except (KeyError, TypeError, ValueError, OverflowError):
            raise DetectorUnavailableError("Roboflow returned an invalid detection response") from None
        return DetectionResult(
            boxes=boxes, inference_ms=(monotonic() - start) * 1000,
            captured_at=captured_at, provider="roboflow", model_id=self.model_id,
        )


def normalize_response(response) -> list[DetectionBox]:
    """Reject the entire malformed inspection rather than omit a bad box."""
    if not isinstance(response, dict) or not isinstance(response.get("predictions"), list):
        raise ValueError("Invalid predictions container")
    boxes = []
    for prediction in response["predictions"]:
        if not isinstance(prediction, dict):
            raise ValueError("Invalid prediction")
        label = prediction["class"]
        if not isinstance(label, str) or not label.strip():
            raise ValueError("Invalid label")
        values = []
        for name in ("x", "y", "width", "height", "confidence"):
            value = prediction[name]
            if isinstance(value, bool):
                raise ValueError("Invalid numeric value")
            value = float(value)
            if not math.isfinite(value):
                raise ValueError("Non-finite numeric value")
            values.append(value)
        x, y, width, height, confidence = values
        if width <= 0 or height <= 0 or not 0 <= confidence <= 1:
            raise ValueError("Invalid box or confidence")
        xyxy = (x - width / 2, y - height / 2, x + width / 2, y + height / 2)
        if not all(math.isfinite(value) for value in xyxy):
            raise ValueError("Non-finite coordinates")
        boxes.append(DetectionBox(label=label, confidence=confidence, xyxy=xyxy))
    return boxes
