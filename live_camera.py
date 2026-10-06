#!/usr/bin/env python
"""Desktop webcam detection with one YOLO worker and a responsive OpenCV preview."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import math
import os
from datetime import datetime, timezone
from backend_publisher import BackendPublisher
from pathlib import Path
import time

DEFAULT_WEIGHTS = str(Path(__file__).resolve().parent / "models" / "best.pt")
COLORS = {"RED": (40, 40, 240), "AMBER": (0, 180, 255),
          "GREEN": (60, 210, 60), "GREY": (180, 180, 180)}


def summarize_result(result=None):
    """Reuse bridge.run_vision's contam-prefix rule and contamination-first verdict.

    Only explicit healthy labels count as healthy, so unrelated classes cannot
    turn an unavailable inspection green. Confidence is never rounded for alerts.
    """
    boxes = []
    if result is not None and result.boxes is not None:
        for cls, conf, xyxy in zip(result.boxes.cls.tolist(),
                                  result.boxes.conf.tolist(),
                                  result.boxes.xyxy.tolist()):
            boxes.append({"label": result.names[int(cls)].lower(),
                          "conf": float(conf), "xyxy": xyxy})
    contaminated = [b for b in boxes if b["label"].startswith("contam")]
    healthy = [b for b in boxes if b["label"].startswith("healthy")]
    max_c = max((b["conf"] for b in contaminated), default=0.0)
    if contaminated:
        verdict, message = "contamination_suspected", "Possible contamination"
        # Below the amber threshold remains unavailable, never green.
        severity = "RED" if max_c >= 0.80 else "AMBER" if max_c >= 0.40 else "GREY"
    elif healthy:
        verdict, message, severity = "no_contamination_seen", "No contamination seen", "GREEN"
    else:
        verdict, message, severity = "no_detection", "Could not inspect", "GREY"
    return dict(verdict=verdict, message=message, severity=severity,
                n_contaminated=len(contaminated), n_healthy=len(healthy),
                max_conf=max((b["conf"] for b in boxes), default=0.0),
                max_contaminated_conf=max_c, boxes=boxes)


def infer(model, frame, args):
    captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    start = time.monotonic()
    options = dict(conf=args.conf, imgsz=416, verbose=False)
    if args.device is not None:
        options["device"] = args.device
    result = model.predict(frame, **options)[0]
    summary = summarize_result(result)
    summary["ms"] = (time.monotonic() - start) * 1000
    summary["shape"] = frame.shape[:2]
    summary["captured_at"] = captured_at
    return summary


def draw_overlay(cv2, frame, summary, ai_fps, age):
    color = COLORS[summary["severity"]]
    h, w = frame.shape[:2]
    source_h, source_w = summary.get("shape", (h, w))
    for box in summary["boxes"]:
        x1, y1, x2, y2 = [int(v * (w / source_w if i % 2 == 0 else h / source_h))
                          for i, v in enumerate(box["xyxy"])]
        box_color = COLORS["AMBER"] if box["label"].startswith("contam") else COLORS["GREEN"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
        cv2.putText(frame, f'{box["label"]} {box["conf"]:.2f}', (x1, max(18, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 1)
    lines = ["SmartPhset Live AI", f'Verdict: {summary["message"]}',
             f'Level: {summary["severity"]}', f'Contaminated: {summary["n_contaminated"]}',
             f'Healthy: {summary["n_healthy"]}',
             f'Contamination confidence: {summary["max_contaminated_conf"]:.2f}',
             f'Inference: {summary.get("ms", 0):.0f} ms', f'AI FPS: {ai_fps:.1f}',
             f'Result age: {age:.1f} s | q: quit']
    cv2.rectangle(frame, (0, 0), (min(w - 1, 470), min(h - 1, 240)), (20, 20, 20), -1)
    for i, line in enumerate(lines):
        cv2.putText(frame, line, (10, 24 + i * 25), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, color, 1, cv2.LINE_AA)
    return frame


def run_camera(args, cv2_module=None, model_factory=None):
    # Lazy imports keep verdict tests independent of torch/OpenCV and hardware.
    if cv2_module is None:
        import cv2 as cv2_module
    if model_factory is None:
        from ultralytics import YOLO
        model_factory = YOLO
    cv2 = cv2_module
    camera = None
    executor = None
    publisher = None
    try:
        weights = Path(args.weights)
        if not weights.is_file():
            raise FileNotFoundError(f"Weights not found: {weights}")
        model = model_factory(str(weights))  # load once; worker is the sole model caller
        camera = cv2.VideoCapture(args.cam)
        if not camera.isOpened():
            raise RuntimeError(f"Cannot open camera {args.cam}; check connection and permissions")
        publisher = BackendPublisher(args.backend_url, args.publish_every,
                                     os.environ.get("SMARTPHSET_AI_INGEST_KEY", ""))
        executor = ThreadPoolExecutor(max_workers=1)
        pending = None
        summary = summarize_result()
        next_inference = 0.0
        last_completed = None
        ai_fps = 0.0
        print("SmartPhset Live AI: point at mushroom bags. Press q or Ctrl+C to quit.")
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                raise RuntimeError("Camera frame unavailable; inspection stopped")
            now = time.monotonic()
            if pending is not None and pending.done():
                summary = pending.result()  # propagate inference failures; finally cleans up
                pending = None
                if last_completed is not None:
                    ai_fps = 1.0 / max(now - last_completed, 1e-9)
                last_completed = now
                if publisher.url:
                    publisher.offer(summary, f"webcam-{args.cam}", now)
            if pending is None and now >= next_inference:
                pending = executor.submit(infer, model, frame.copy(), args)
                next_inference = now + 1.0 / args.fps
            age = now - last_completed if last_completed is not None else 0.0
            cv2.imshow("SmartPhset Live AI", draw_overlay(cv2, frame, summary, ai_fps, age))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        if publisher is not None:
            publisher.close()
        try:
            if camera is not None:
                camera.release()
        finally:
            try:
                cv2.destroyAllWindows()
            finally:
                if executor is not None:
                    executor.shutdown(wait=True, cancel_futures=True)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cam", type=int, default=0)
    parser.add_argument("--conf", type=float, default=0.4)
    parser.add_argument("--fps", type=float, default=5, help="maximum inference FPS; preview runs independently")
    parser.add_argument("--weights", default=DEFAULT_WEIGHTS)
    parser.add_argument("--device", default=None, help="optional Ultralytics device, e.g. cpu or 0")
    parser.add_argument("--backend-url", default=os.environ.get("SMARTPHSET_BACKEND_URL"),
                        help="optional backend base URL; unset disables publishing")
    parser.add_argument("--publish-every", type=float, default=5, help="seconds between periodic snapshots")
    args = parser.parse_args(argv)
    if not math.isfinite(args.publish_every) or args.publish_every <= 0:
        parser.error("--publish-every must be finite and greater than zero")
    if args.backend_url:
        from urllib.parse import urlsplit
        parsed = urlsplit(args.backend_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            parser.error("--backend-url must be an HTTP(S) base URL without credentials, query or fragment")
    if not math.isfinite(args.fps) or args.fps <= 0:
        parser.error("--fps must be finite and greater than zero")
    if not math.isfinite(args.conf) or not 0 <= args.conf <= 1:
        parser.error("--conf must be between 0 and 1")
    return args


def main():
    args = parse_args()
    try:
        run_camera(args)
    except (RuntimeError, OSError, ImportError) as exc:
        raise SystemExit(f"SmartPhset Live AI: {exc}") from exc


if __name__ == "__main__":
    main()
