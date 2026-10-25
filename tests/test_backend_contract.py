"""Golden payload shared with the Spring DTO integration tests."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import UUID
from backend_publisher import detection_payload
from detectors import DetectionBox
from live_camera import summarize_detections


class BackendContractTests(unittest.TestCase):
    def test_publisher_matches_shared_spring_fixture(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/ai-detection.json').read_text())
        summary=summarize_detections([
            DetectionBox('Healthy',.99,(500.,180.,800.,650.)),
            DetectionBox('Contaminated',.799999999,(120.,180.,450.,650.))])
        summary.update(shape=(720,1280),captured_at=fixture['captured_at'],ms=83.7)
        with patch('backend_publisher.uuid4',return_value=UUID(fixture['event_id'])):
            self.assertEqual(detection_payload(summary,'esp32-cam'),fixture)

    def test_duplicate_ack_is_success(self):
        from unittest.mock import MagicMock
        from backend_publisher import BackendPublisher
        opener=MagicMock()
        with patch('backend_publisher.threading.Thread'):
            publisher=BackendPublisher('http://localhost:9090',opener=opener)
            try:
                for status in (201,200):
                    opener.return_value.__enter__.return_value.status=status
                    with patch('backend_publisher.logger.warning') as warning:
                        publisher._send(json.loads((Path(__file__).parent/'fixtures/ai-detection.json').read_text()))
                        warning.assert_not_called()
            finally:publisher.close()
