"""Mocked SDK contract tests; no API key or external request is required."""

import asyncio
from contextlib import ExitStack
from datetime import datetime
import io
import sys
from types import ModuleType
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
from requests.exceptions import ConnectionError as RequestsConnectionError

from detectors import Detector
from detectors.roboflow_detector import (
    DEFAULT_API_URL, DEFAULT_MODEL_ID, DetectorUnavailableError, RoboflowDetector,
)
from live_camera import summarize_detections


class SDKError(Exception):
    pass


class AsyncClientError(Exception):
    pass


def prediction(label="Contaminated", confidence=0.9123456789):
    return dict(x=320, y=240, width=100, height=200,
                confidence=confidence, **{"class": label})


class RoboflowTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        sdk, http, errors, aiohttp = (ModuleType(name) for name in
                                    ("inference_sdk", "inference_sdk.http",
                                     "inference_sdk.http.errors", "aiohttp"))
        self.factory = sdk.InferenceHTTPClient = MagicMock()
        self.configuration = sdk.InferenceConfiguration = MagicMock()
        self.client = self.factory.return_value.configure.return_value
        self.client.infer_async = AsyncMock(return_value={"predictions": [prediction()]})
        errors.HTTPClientError = SDKError
        aiohttp.ClientError = AsyncClientError
        stack.enter_context(patch.dict(sys.modules, {
            "inference_sdk": sdk, "inference_sdk.http": http,
            "inference_sdk.http.errors": errors, "aiohttp": aiohttp,
        }))
        # Any accidentally introduced real request fails the test immediately.
        stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")))
        stack.enter_context(patch("requests.sessions.Session.request",
                                  side_effect=AssertionError("HTTP forbidden")))
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def detector(self, **kwargs):
        return RoboflowDetector(api_key="unit-test-secret", **kwargs)

    def test_construct_once_and_pass_numpy_directly(self):
        detector = self.detector()
        self.assertIsInstance(detector, Detector)
        detector.detect(self.frame)
        detector.detect(self.frame)
        self.factory.assert_called_once_with(api_url=DEFAULT_API_URL, api_key="unit-test-secret")
        self.configuration.assert_called_once_with(
            api_key_transport="header", confidence_threshold=0.4, client_downsizing_disabled=True)
        self.assertEqual(self.client.infer_async.await_count, 2)
        for call in self.client.infer_async.await_args_list:
            self.assertIs(call.args[0], self.frame)
            self.assertEqual(call.kwargs, {"model_id": DEFAULT_MODEL_ID})
        self.client.infer.assert_not_called()

    def test_custom_config(self):
        detector = self.detector(model_id="custom/2", api_url="http://localhost:9001", confidence=0.25)
        detector.detect(self.frame)
        self.factory.assert_called_once_with(api_url="http://localhost:9001", api_key="unit-test-secret")
        self.assertEqual(self.configuration.call_args.kwargs["confidence_threshold"], 0.25)
        self.assertEqual(self.client.infer_async.await_args.kwargs["model_id"], "custom/2")

    def test_environment_key_and_missing_key(self):
        with patch.dict("os.environ", {"ROBOFLOW_API_KEY": "environment-test-key"}):
            RoboflowDetector()
        self.assertEqual(self.factory.call_args.kwargs["api_key"], "environment-test-key")
        self.factory.reset_mock()
        with patch.dict("os.environ", {}, clear=True):
            for key in (None, "", "  "):
                with self.assertRaisesRegex(ValueError, "ROBOFLOW_API_KEY is required"):
                    RoboflowDetector(api_key=key)
        self.factory.assert_not_called()

    def test_classes_coordinates_and_precision(self):
        detector = self.detector()
        for label, severity in (("Healthy", "GREEN"), ("Contaminated", "RED"), ("Other", "GREY")):
            with self.subTest(label=label):
                self.client.infer_async.return_value = {"predictions": [prediction(label)]}
                result = detector.detect(self.frame)
                self.assertEqual(result.boxes[0].label, label.lower())
                self.assertEqual(result.boxes[0].confidence, 0.9123456789)
                self.assertEqual(result.boxes[0].xyxy, (270.0, 140.0, 370.0, 340.0))
                self.assertTrue(all(isinstance(value, float) for value in result.boxes[0].xyxy))
                self.assertEqual(summarize_detections(result.boxes)["severity"], severity)

    def test_multiple_predictions_keep_order_and_contamination_wins(self):
        detector = self.detector()
        for predictions in ([prediction("Healthy", 0.99), prediction("Contaminated", 0.79)],
                            [prediction("Contaminated", 0.79), prediction("Healthy", 0.99)]):
            self.client.infer_async.return_value = {"predictions": predictions}
            result = detector.detect(self.frame)
            self.assertEqual(len(result.boxes), 2)
            self.assertEqual(summarize_detections(result.boxes)["severity"], "AMBER")

    def test_empty_predictions(self):
        self.client.infer_async.return_value = {"predictions": []}
        result = self.detector().detect(self.frame)
        self.assertEqual(result.boxes, [])
        self.assertEqual(summarize_detections(result.boxes)["severity"], "GREY")

    def test_malformed_response_is_unavailable(self):
        detector = self.detector()
        malformed = [None, [], {}, {"predictions": None}, {"predictions": {}},
                     {"predictions": [None]}, {"predictions": [{}]}]
        for field, value in (("class", None), ("class", ""), ("x", "invalid"),
                             ("y", float("nan")), ("width", -1), ("height", 0),
                             ("confidence", 1.1), ("confidence", -0.1),
                             ("confidence", True), ("height", float("inf"))):
            item = prediction()
            item[field] = value
            # A valid Healthy box must not hide a malformed contamination box.
            malformed.append({"predictions": [prediction("Healthy"), item]})
        for response in malformed:
            with self.subTest(response=response):
                self.client.infer_async.return_value = response
                with self.assertRaisesRegex(DetectorUnavailableError, "invalid detection response"):
                    detector.detect(self.frame)

    def test_sdk_network_and_timeout_errors_are_safe(self):
        detector = self.detector()
        for error in (SDKError, AsyncClientError, RequestsConnectionError, OSError, TimeoutError):
            with self.subTest(error=error):
                self.client.infer_async.side_effect = error("unit-test-secret should not escape")
                with self.assertRaises(DetectorUnavailableError) as raised:
                    detector.detect(self.frame)
                self.assertNotIn("unit-test-secret", str(raised.exception))
                self.assertTrue(raised.exception.__suppress_context__)

    def test_deadline_cancels_work(self):
        cancelled = []

        async def slow(*args, **kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

        self.client.infer_async.side_effect = slow
        detector = self.detector(timeout=0.01)
        with self.assertRaises(DetectorUnavailableError):
            detector.detect(self.frame)
        self.assertEqual(cancelled, [True])
        self.client.infer_async.assert_awaited_once()

    def test_metadata_and_no_output(self):
        output = io.StringIO()
        with patch("sys.stdout", output), patch("sys.stderr", output):
            detector = self.detector()
            with patch("detectors.roboflow_detector.monotonic", side_effect=[10, 10.125]):
                result = detector.detect(self.frame)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual((result.provider, result.model_id, result.inference_ms),
                         ("roboflow", DEFAULT_MODEL_ID, 125.0))
        self.assertTrue(result.captured_at.endswith("Z"))
        self.assertEqual(datetime.fromisoformat(result.captured_at).utcoffset().total_seconds(), 0)

    def test_invalid_configuration(self):
        for options in ({"confidence": float("nan")}, {"confidence": -1},
                        {"confidence": 1.1}, {"timeout": 0}, {"timeout": float("inf")}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.detector(**options)


class InstalledSDKTests(unittest.TestCase):
    """Exercise installed SDK encoding/auth, replacing only outbound transport."""

    def test_actual_sdk_encodes_numpy_and_uses_header_auth(self):
        from inference_sdk import InferenceHTTPClient

        transport = AsyncMock(return_value=[{"predictions": [prediction()]}])
        with patch("inference_sdk.http.client.execute_requests_packages_async", transport), \
                patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
            detector = RoboflowDetector(api_key="installed-sdk-test-key", confidence=0.63)
            result = detector.detect(np.zeros((480, 640, 3), dtype=np.uint8))
        self.assertIsInstance(detector.client, InferenceHTTPClient)
        transport.assert_awaited_once()
        request, = transport.await_args.kwargs["requests_data"]
        self.assertEqual(request.url, DEFAULT_API_URL + "/" + DEFAULT_MODEL_ID)
        self.assertEqual(request.headers["Authorization"], "Bearer installed-sdk-test-key")
        self.assertNotIn("api_key", request.parameters)
        self.assertIsNone(request.payload)
        self.assertEqual(request.parameters["confidence"], 0.63)
        self.assertTrue(request.data)
        self.assertEqual(result.boxes[0].xyxy, (270.0, 140.0, 370.0, 340.0))

    def test_actual_sdk_failure_and_session_cancellation(self):
        from inference_sdk.http.errors import HTTPClientError

        with patch("inference_sdk.http.client.execute_requests_packages_async",
                   AsyncMock(side_effect=HTTPClientError("credential must not escape"))):
            with self.assertRaisesRegex(DetectorUnavailableError, "inference unavailable"):
                RoboflowDetector(api_key="installed-sdk-test-key").detect(np.zeros((4, 4, 3), dtype=np.uint8))

        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        request_context = MagicMock()

        async def wait_forever():
            await asyncio.Event().wait()

        request_context.__aenter__ = AsyncMock(side_effect=wait_forever)
        request_context.__aexit__ = AsyncMock(return_value=False)
        session.post.return_value = request_context
        with patch("inference_sdk.http.utils.executors.aiohttp.ClientSession", return_value=session), \
                patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
            detector = RoboflowDetector(api_key="installed-sdk-test-key", timeout=0.01)
            with self.assertRaises(DetectorUnavailableError):
                detector.detect(np.zeros((4, 4, 3), dtype=np.uint8))
        session.__aexit__.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
