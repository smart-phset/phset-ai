"""Persistent authenticated inference service. Bind privately; expose through Next only."""
import hmac
import json
import os
import re
import secrets
import signal
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

from live_camera import DEFAULT_WEIGHTS, infer_detector, draw_overlay, open_video_source
from live_stream import LatestFrame
from backend_publisher import BackendPublisher
from detectors.local_ultralytics import LocalUltralyticsDetector

MAX_JPEG = 512 * 1024


class ServiceError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def jpeg_size(data):
    """Read dimensions before decoding to bound decompression memory."""
    if not data.startswith(b'\xff\xd8'):
        raise ServiceError(415, 'jpeg_required')
    i = 2
    while i + 4 <= len(data):
        if data[i] != 255:
            break
        marker = data[i + 1]
        i += 2
        if marker == 255:
            i -= 1
            continue
        length = int.from_bytes(data[i:i + 2], 'big')
        if length < 2 or i + length > len(data):
            break
        if marker in (192, 193, 194):
            if length < 8:
                break
            h, w = struct.unpack('>HH', data[i + 3:i + 7])
            if not (1 <= w <= 1280 and 1 <= h <= 1280 and w * h <= 921600):
                raise ServiceError(413, 'frame_dimensions_exceeded')
            return w, h
        i += length
    raise ServiceError(415, 'invalid_jpeg')


class Sessions:
    def __init__(self, detector, sources=None, limit=16, ttl=60, cv2=None):
        self.detector, self.sources = detector, sources or {}
        self.limit, self.ttl, self.cv2 = limit, ttl, cv2
        self.lock = threading.RLock()
        self.inference = threading.Lock()  # YOLO is shared and not thread safe. Zero waiting jobs.
        self.sessions, self.workers = {}, {}
        self.closed = threading.Event()

    def create(self, owner, source):
        with self.lock:
            self.expire()
            if source != 'browser' and source not in self.sources:
                raise ServiceError(404, 'unknown_source')
            if len(self.sessions) >= self.limit:
                raise ServiceError(429, 'session_limit')
            worker = self.workers.get(source)
            if worker and (worker.state.stopped.is_set() or not worker.is_alive()):
                if worker.is_alive():
                    raise ServiceError(503, 'source_stopping_retry')
                del self.workers[source]
            sid = secrets.token_urlsafe(24)
            self.sessions[sid] = dict(owner=owner, source=source, identity=secrets.token_urlsafe(16), revision=0, ai=False, touched=time.monotonic(), result=None, last=0)
            if source != 'browser' and source not in self.workers:
                worker = SharedWorker(self, source)
                self.workers[source] = worker
                worker.start()
            return sid

    def get(self, owner, sid):
        with self.lock:
            session = self.sessions.get(sid)
            if not session or session['owner'] != owner or time.monotonic() - session['touched'] > self.ttl:
                raise ServiceError(404, 'session_not_found')
            session['touched'] = time.monotonic()
            return session

    def expire(self):
        with self.lock:
            now = time.monotonic()
            self.sessions = {k: v for k, v in self.sessions.items() if now - v['touched'] <= self.ttl}
            used = {v['source'] for v in self.sessions.values()}
            for source, worker in list(self.workers.items()):
                if source not in used:
                    worker.state.close()
                    # Retain until thread exits: never overlap capture owners.
                    if not worker.is_alive():
                        del self.workers[source]

    def detect(self, frame):
        if not self.inference.acquire(False):
            raise ServiceError(429, 'inference_busy')
        try:
            return infer_detector(self.detector, frame)
        finally:
            self.inference.release()

    def snapshot(self, owner, sid):
        with self.lock:
            s = self.get(owner, sid)
            worker = self.workers.get(s['source'])
            health = worker.state.health() if worker else None
            return dict(session_id=sid, source_id=('browser-' + s['identity'] if s['source'] == 'browser' else s['source']), analyzing=s['ai'],
                        status=(health['status'] if health and not health['streaming'] else 'DETECTING' if s['ai'] else 'LIVE'),
                        detection=s['result'] if s['ai'] and (not health or health['streaming']) else None)


class SharedWorker(threading.Thread):
    def __init__(self, manager, source):
        super().__init__(daemon=True)
        self.manager, self.source = manager, source
        self.state = LatestFrame(source)

    def run(self):
        m, capture = self.manager, None
        publisher = BackendPublisher(os.getenv('SMARTPHSET_BACKEND_URL'), ingest_key=os.getenv('SMARTPHSET_AI_INGEST_KEY', ''))
        try:
            while not self.state.stopped.is_set():
                if capture is None:
                    value = m.sources[self.source]
                    capture, _ = open_video_source(m.cv2, SimpleNamespace(source=value if isinstance(value, str) else None, cam=value, serve=True))
                ok, frame = capture.read()
                if not ok:
                    self.state.unavailable()
                    capture.release()
                    capture = None
                    self.state.stopped.wait(2)
                    continue
                with m.lock:
                    viewers = [(s, s['revision']) for s in m.sessions.values() if s['source'] == self.source and s['ai']]
                if viewers:
                    try:
                        result = m.detect(frame)
                        with m.lock:
                            for s, revision in viewers:
                                if s['ai'] and s['revision'] == revision:
                                    s['result'] = result
                        publisher.offer(result, self.source)
                        draw_overlay(m.cv2, frame, result, 2, 0)
                    except ServiceError:
                        pass
                self.state.publish(m.cv2, frame)
                self.state.stopped.wait(.5)
        except Exception:
            self.state.unavailable('inference_unavailable')
        finally:
            if capture is not None:
                capture.release()
            publisher.close()


def server(manager, key, host='127.0.0.1', port=8002):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def handle_request(self):
            self.connection.settimeout(10)
            try:
                if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + key):
                    raise ServiceError(401, 'unauthorized')
                owner = self.headers.get('X-Camera-Owner', '')
                if not re.fullmatch(r'[a-f0-9]{64}', owner):
                    raise ServiceError(401, 'owner_required')
                parts = self.path.strip('/').split('/')
                if self.command == 'GET' and parts == ['sources']:
                    with manager.lock:
                        return self.reply(200, {name: manager.workers[name].state.health() if name in manager.workers else {'status': 'idle', 'streaming': False} for name in manager.sources})
                length = int(self.headers.get('Content-Length', '0'))
                if length < 0 or length > MAX_JPEG:
                    raise ServiceError(413, 'frame_too_large')
                if self.command == 'DELETE' and parts == ['sessions']:
                    with manager.lock:
                        manager.sessions = {k: v for k, v in manager.sessions.items() if v['owner'] != owner}
                        manager.expire()
                    return self.reply(200, {'status': 'stopped'})
                if self.command == 'POST' and parts == ['sessions']:
                    if length > 1024:
                        raise ServiceError(413, 'request_too_large')
                    data = json.loads(self.rfile.read(length))
                    sid = manager.create(owner, data['source_id'])
                    return self.reply(201, manager.snapshot(owner, sid))
                if len(parts) not in (2, 3) or parts[0] != 'sessions':
                    raise ServiceError(404, 'not_found')
                sid = parts[1]
                s = manager.get(owner, sid)
                action = parts[2] if len(parts) == 3 else ''
                if self.command == 'DELETE' and not action:
                    with manager.lock:
                        manager.sessions.pop(sid, None)
                        manager.expire()
                    return self.reply(200, {'status': 'stopped'})
                if self.command == 'POST' and action in ('start', 'stop'):
                    data = json.loads(self.rfile.read(length) or b'{}')
                    revision = data.get('revision')
                    if type(revision) is not int or revision < 1:
                        raise ServiceError(400, 'revision_required')
                    with manager.lock:
                        if revision > s['revision']:
                            s['revision'] = revision
                            s['ai'] = action == 'start'
                            s['result'] = None
                    return self.reply(200, manager.snapshot(owner, sid))
                if self.command == 'POST' and action == 'frames':
                    if s['source'] != 'browser' or not s['ai']:
                        raise ServiceError(409, 'analysis_not_started')
                    revision = int(self.headers.get('X-Camera-Revision', '0'))
                    if revision != s['revision']:
                        raise ServiceError(409, 'stale_frame')
                    if self.headers.get('Content-Type') != 'image/jpeg':
                        raise ServiceError(415, 'jpeg_required')
                    with manager.lock:
                        if time.monotonic() - s['last'] < .2:
                            raise ServiceError(429, 'sampling_limit')
                        s['last'] = time.monotonic()
                    data = self.rfile.read(length)
                    jpeg_size(data)
                    import numpy as np
                    frame = manager.cv2.imdecode(np.frombuffer(data, dtype=np.uint8), manager.cv2.IMREAD_COLOR)
                    if frame is None:
                        raise ServiceError(415, 'invalid_jpeg')
                    result = manager.detect(frame)
                    with manager.lock:
                        if s['ai'] and revision == s['revision']:
                            s['result'] = result
                    return self.reply(200, manager.snapshot(owner, sid))
                if self.command == 'GET' and action == 'stream' and s['source'] != 'browser':
                    state = manager.workers[s['source']].state
                    with state.condition:
                        state.condition.wait_for(lambda: state.health()['streaming'] or state.status != 'starting', timeout=6)
                    if not state.health()['streaming']:
                        raise ServiceError(503, 'camera_unavailable')
                    self.send_response(200)
                    self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    for part in state.frames():
                        with manager.lock:
                            if sid not in manager.sessions:
                                break
                        self.wfile.write(part)
                        self.wfile.flush()
                    return
                if self.command == 'GET' and not action:
                    return self.reply(200, manager.snapshot(owner, sid))
                raise ServiceError(404, 'not_found')
            except ServiceError as e:
                self.reply(e.status, {'error': e.message})
            except (ValueError, KeyError, TypeError):
                self.reply(400, {'error': 'invalid_request'})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.reply(503, {'error': 'inference_unavailable'})
            finally:
                self.close_connection = True

        def reply(self, status, value):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = do_DELETE = handle_request

    class BoundedServer(ThreadingHTTPServer):
        daemon_threads = True
        slots = threading.BoundedSemaphore(32)

        def process_request(self, request, address):
            if not self.slots.acquire(False):
                request.close()
                return
            try:
                super().process_request(request, address)
            except Exception:
                self.slots.release()
                raise

        def process_request_thread(self, request, address):
            try:
                super().process_request_thread(request, address)
            finally:
                self.slots.release()

    return BoundedServer((host, port), Handler)


def main():
    key = os.environ['SMARTPHSET_AI_SERVICE_KEY']
    if len(key) < 32:
        raise ValueError('Service key must contain at least 32 characters')
    # Operator allowlist only. No URL can arrive from a viewer or registry request.
    sources = json.loads(os.getenv('SMARTPHSET_CAMERA_SOURCES', '{}'))
    for name, value in sources.items():
        if name == 'browser' or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', name) or not (type(value) is int and 0 <= value <= 16 or isinstance(value, str) and value.startswith(('http://', 'https://', 'rtsp://'))):
            raise ValueError('Invalid configured camera')
    os.environ.setdefault('OPENCV_IO_MAX_IMAGE_PIXELS', '921600')
    import cv2
    detector = LocalUltralyticsDetector(os.getenv('SMARTPHSET_WEIGHTS') or DEFAULT_WEIGHTS, float(os.getenv('SMARTPHSET_CONFIDENCE', '.4')))
    manager = Sessions(detector, sources, limit=max(1, min(64, int(os.getenv('SMARTPHSET_AI_MAX_SESSIONS', '16')))), ttl=60, cv2=cv2)
    def reap():
        while not manager.closed.wait(2):
            manager.expire()
    threading.Thread(target=reap, daemon=True).start()
    http = server(manager, key)
    def shutdown(*_):
        threading.Thread(target=http.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        http.serve_forever()
    finally:
        manager.closed.set()
        workers = list(manager.workers.values())
        for worker in workers:
            worker.state.close()
        deadline = time.monotonic() + 6
        for worker in workers:
            worker.join(max(0, deadline - time.monotonic()))
        http.server_close()


if __name__ == '__main__':
    main()
