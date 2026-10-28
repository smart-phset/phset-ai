"""Bounded latest-frame MJPEG fan-out. HTTP handlers never capture or infer."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def mjpeg_part(jpeg):
    return (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(jpeg)).encode("ascii") + b"\r\n\r\n" + jpeg + b"\r\n")


class LatestFrame:
    def __init__(self, camera, stale_after=10):
        self.camera = camera
        self.stale_after = stale_after
        self.condition = threading.Condition()
        self.jpeg = None
        self.sequence = 0
        self.updated = 0
        self.status = "starting"
        self.stopped = threading.Event()

    def publish(self, cv2, annotated_frame, quality=80):
        ok, encoded = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("Could not encode live frame")
        with self.condition:
            self.jpeg = encoded.tobytes()
            self.sequence += 1
            self.updated = time.monotonic()
            self.status = "ok"
            self.condition.notify_all()

    def unavailable(self, status="camera_unavailable"):
        with self.condition:
            self.status = status
            self.jpeg = None
            self.condition.notify_all()

    def health(self):
        with self.condition:
            streaming = (not self.stopped.is_set() and self.status == "ok"
                         and self.jpeg is not None and time.monotonic() - self.updated < self.stale_after)
            return {"status": self.status if self.status != "ok" or streaming else "stalled",
                    "camera": self.camera, "streaming": streaming}

    def frames(self):
        sequence = -1
        while not self.stopped.is_set():
            with self.condition:
                self.condition.wait_for(lambda: self.stopped.is_set() or
                                        (self.jpeg is not None and self.sequence != sequence), timeout=1)
                if self.stopped.is_set() or self.status not in ("starting", "ok"):
                    return
                if self.status == "ok" and time.monotonic() - self.updated >= self.stale_after:
                    return
                if self.jpeg is None or self.sequence == sequence:
                    if self.status == "ok" and time.monotonic() - self.updated >= self.stale_after:
                        return
                    continue
                sequence, jpeg = self.sequence, self.jpeg
            yield mjpeg_part(jpeg)

    def close(self):
        self.stopped.set()
        with self.condition:
            self.condition.notify_all()


def streaming_server(state, host="127.0.0.1", port=8001):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # No URLs, request headers or credentials in logs.

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps(state.health()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/stream.mjpg":
                if not state.health()["streaming"]:
                    self.send_error(503, "Camera unavailable")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("X-SmartPhset-Camera-Id", state.camera)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.connection.settimeout(5)
                frames = state.frames()
                try:
                    for part in frames:
                        self.wfile.write(part)
                        self.wfile.flush()
                except (OSError, TimeoutError):
                    pass
                finally:
                    frames.close()
                    self.close_connection = True
            else:
                self.send_error(404)

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
