"""Bounded, best-effort JSON publishing on one background worker."""
from datetime import datetime, timezone
import json
import logging
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import URLError
from uuid import uuid4

logger = logging.getLogger(__name__)


def detection_payload(summary, camera_id):
    height, width = summary['shape']
    return {
        'event_id': str(uuid4()), 'camera_id': camera_id,
        'captured_at': summary.get('captured_at', datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')),
        **{key: summary[key] for key in ('verdict', 'severity', 'message', 'n_contaminated',
                                        'n_healthy', 'max_conf', 'max_contaminated_conf')},
        'width': int(width), 'height': int(height), 'inference_ms': round(summary.get('ms', 0)),
        'boxes': [{'label': b['label'], 'conf': float(b['conf']),
                   'xyxy': [int(v) for v in b['xyxy']]} for b in summary['boxes']],
    }


class BackendPublisher:
    """One in-flight request and one replaceable pending snapshot.

    Failed events are dropped. Future snapshots report current state. Shutdown
    discards pending work and never waits for the HTTP request on the camera thread.
    """
    def __init__(self, backend_url=None, publish_every=5, ingest_key='', opener=urlopen):
        self.url = backend_url.rstrip('/') + '/api/ai/detections' if backend_url else None
        self.interval, self.key, self.opener = publish_every, ingest_key, opener
        self.last_state = self.last_publish = None
        self.condition = threading.Condition()
        self.pending = None
        self.closed = False
        self.worker = None
        if self.url:
            self.worker = threading.Thread(target=self._run, name='ai-backend-publisher', daemon=True)
            self.worker.start()

    def offer(self, summary, camera_id, now=None):
        if not self.url:
            return False
        now = time.monotonic() if now is None else now
        state = (summary['verdict'], summary['severity'])
        if state == self.last_state and self.last_publish is not None and now - self.last_publish < self.interval:
            return False
        payload = detection_payload(summary, camera_id)
        with self.condition:
            if self.closed:
                return False
            self.pending = payload
            self.last_state, self.last_publish = state, now
            self.condition.notify()
        return True

    def _send(self, payload):
        headers = {'Content-Type': 'application/json'}
        if self.key:
            headers['X-SmartPhset-AI-Key'] = self.key
        try:
            request = Request(self.url, data=json.dumps(payload, allow_nan=False).encode('utf-8'),
                              headers=headers, method='POST')
            with self.opener(request, timeout=3) as response:
                if response.status >= 400:
                    logger.warning('Backend publish failed: HTTP %s', response.status)
        except (URLError, OSError, TimeoutError, ValueError) as exc:
            logger.warning('Backend publish failed: %s', exc)

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or self.pending is not None)
                if self.closed:
                    return
                payload, self.pending = self.pending, None
            self._send(payload)

    def close(self):
        with self.condition:
            self.closed = True
            self.pending = None
            self.condition.notify()
