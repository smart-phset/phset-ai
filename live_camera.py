#!/usr/bin/env python
"""Live SmartPhset detection from webcam or network video stream."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import math
import os
from pathlib import Path
import time

from backend_publisher import BackendPublisher
from detectors.types import DetectionBox
from detectors.local_ultralytics import LocalUltralyticsDetector


DEFAULT_WEIGHTS = str(
    Path(__file__).resolve().parent / "models" / "best.pt"
)

COLORS = {
    "RED": (40, 40, 240),
    "AMBER": (0, 180, 255),
    "GREEN": (60, 210, 60),
    "GREY": (180, 180, 180),
}


def summarize_result(result=None):
    """Compatibility adapter for existing Ultralytics result callers."""
    boxes = []
    if result is not None and result.boxes is not None:
        for cls, conf, xyxy in zip(
            result.boxes.cls.tolist(),
            result.boxes.conf.tolist(),
            result.boxes.xyxy.tolist(),
        ):
            boxes.append(DetectionBox(
                label=result.names[int(cls)],
                confidence=float(conf),
                xyxy=tuple(xyxy),
            ))
    return summarize_detections(boxes)


def summarize_detections(boxes: list[DetectionBox]) -> dict:
    """Apply SmartPhset's contamination-first policy to normalized boxes."""
    contaminated = [b for b in boxes if b.label.startswith("contam")]
    healthy = [b for b in boxes if b.label.startswith("healthy")]
    max_c = max((b.confidence for b in contaminated), default=0.0)

    if contaminated:
        verdict = "contamination_suspected"
        message = "Possible contamination"

        severity = (
            "RED"
            if max_c >= 0.80
            else "AMBER"
            if max_c >= 0.40
            else "GREY"
        )

    elif healthy:
        verdict = "no_contamination_seen"
        message = "No contamination seen"
        severity = "GREEN"

    else:
        verdict = "no_detection"
        message = "Could not inspect"
        severity = "GREY"

    return {
        "verdict": verdict,
        "message": message,
        "severity": severity,
        "n_contaminated": len(contaminated),
        "n_healthy": len(healthy),
        "max_conf": max(
            (b.confidence for b in boxes),
            default=0.0,
        ),
        "max_contaminated_conf": max_c,
        "boxes": [
            {"label": b.label, "conf": b.confidence, "xyxy": list(b.xyxy)}
            for b in boxes
        ],
    }


def infer(model, frame, args):
    """Compatibility entry point for callers supplying an already-loaded YOLO."""
    detector = LocalUltralyticsDetector(
        args.weights, args.conf, args.device,
        model_factory=lambda weights: model,
    )
    return infer_detector(detector, frame)


def infer_detector(detector, frame):
    result = detector.detect(frame)
    summary = summarize_detections(result.boxes)
    summary["ms"] = result.inference_ms
    summary["shape"] = frame.shape[:2]
    summary["captured_at"] = result.captured_at
    return summary


def draw_overlay(
    cv2,
    frame,
    summary,
    ai_fps,
    age,
):
    color = COLORS[summary["severity"]]

    h, w = frame.shape[:2]

    source_h, source_w = summary.get(
        "shape",
        (h, w),
    )

    for box in summary["boxes"]:

        x1, y1, x2, y2 = [
            int(
                v * (
                    w / source_w
                    if i % 2 == 0
                    else h / source_h
                )
            )
            for i, v in enumerate(
                box["xyxy"]
            )
        ]

        box_color = (
            COLORS["AMBER"]
            if box["label"].startswith("contam")
            else COLORS["GREEN"]
        )

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            box_color,
            2,
        )

        cv2.putText(
            frame,
            f'{box["label"]} {box["conf"]:.2f}',
            (x1, max(18, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            box_color,
            1,
        )

    lines = [
        "SmartPhset Live AI",
        f'Verdict: {summary["message"]}',
        f'Level: {summary["severity"]}',
        f'Contaminated: {summary["n_contaminated"]}',
        f'Healthy: {summary["n_healthy"]}',
        (
            "Contamination confidence: "
            f'{summary["max_contaminated_conf"]:.2f}'
        ),
        f'Inference: {summary.get("ms", 0):.0f} ms',
        f'AI FPS: {ai_fps:.1f}',
        f'Result age: {age:.1f} s | q: quit',
    ]

    cv2.rectangle(
        frame,
        (0, 0),
        (
            min(w - 1, 470),
            min(h - 1, 240),
        ),
        (20, 20, 20),
        -1,
    )

    for i, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (10, 24 + i * 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            1,
            cv2.LINE_AA,
        )

    return frame


def open_video_source(cv2, args):
    """
    Open either:

    --cam 0
    or
    --source http://ESP32-IP:81/stream
    """

    if args.source:
        video_source = args.source
        source_name = "esp32-cam"

        print(
            f"Connecting to network stream: "
            f"{video_source}"
        )
    else:
        video_source = args.cam
        source_name = f"webcam-{args.cam}"

        print(
            f"Opening local camera: "
            f"{args.cam}"
        )

    camera = cv2.VideoCapture(
        video_source
    )

    # May reduce latency on backends that support it.
    try:
        camera.set(
            cv2.CAP_PROP_BUFFERSIZE,
            1,
        )
    except Exception:
        pass

    return camera, source_name


def build_detector(args, model_factory=None):
    """Construct only the selected provider; hosted mode needs no local weights."""
    if args.model_provider == "local":
        weights = Path(args.weights)
        if not weights.is_file():
            raise FileNotFoundError(f"Weights not found: {weights}")
        print(f"Loading YOLO model: {weights}")
        return LocalUltralyticsDetector(
            str(weights), args.conf, args.device, args.imgsz,
            model_factory=model_factory,
        )
    if args.model_provider == "roboflow":
        if not os.environ.get("ROBOFLOW_API_KEY", "").strip():
            raise ValueError("ROBOFLOW_API_KEY is required for the Roboflow provider")
        from detectors.roboflow_detector import RoboflowDetector
        return RoboflowDetector(model_id=args.roboflow_model_id,
                                api_url=args.roboflow_api_url, confidence=args.conf)
    raise ValueError("Unknown model provider")


def unavailable_summary(frame):
    summary = summarize_detections([])
    summary["shape"] = frame.shape[:2]
    return summary


def run_camera(
    args,
    cv2_module=None,
    model_factory=None,
):
    # Lazy imports keep tests independent
    # of torch/OpenCV and camera hardware.

    if cv2_module is None:
        import cv2 as cv2_module

    cv2 = cv2_module

    camera = None
    executor = None
    publisher = None
    detector = None
    hosted = args.model_provider == "roboflow"

    try:
        detector = build_detector(args, model_factory)

        camera, camera_name = (
            open_video_source(
                cv2,
                args,
            )
        )

        if not camera.isOpened():
            if args.source:
                raise RuntimeError(
                    "Cannot open network video "
                    f"stream: {args.source}"
                )

            raise RuntimeError(
                f"Cannot open camera {args.cam}; "
                "check connection and permissions"
            )

        print(
            f"Video source opened: "
            f"{camera_name}"
        )

        publisher = BackendPublisher(
            args.backend_url,
            args.publish_every,
            os.environ.get(
                "SMARTPHSET_AI_INGEST_KEY",
                "",
            ),
        )

        executor = ThreadPoolExecutor(
            max_workers=1
        )

        pending = None
        summary = summarize_result()

        next_inference = 0.0
        last_completed = None
        ai_fps = 0.0
        submitted_at = None
        result_frame_time = None
        stale_after = max(5.0, 2.0 / args.fps)

        print()
        print(
            "SmartPhset Live AI running."
        )
        print(
            "Point the ESP32-CAM at "
            "mushroom bags."
        )
        print(
            "Press q or Ctrl+C to quit."
        )
        print()

        while True:

            ok, frame = camera.read()

            # ---------------------------------
            # Stream reconnect support
            # ---------------------------------
            if not ok or frame is None:

                if not args.source:
                    raise RuntimeError(
                        "Camera frame unavailable; "
                        "inspection stopped"
                    )

                print(
                    "ESP32-CAM stream lost. "
                    "Reconnecting..."
                )

                camera.release()

                time.sleep(
                    args.reconnect_delay
                )

                camera, camera_name = (
                    open_video_source(
                        cv2,
                        args,
                    )
                )

                if not camera.isOpened():
                    print(
                        "Reconnect failed. "
                        "Trying again..."
                    )

                    camera.release()
                    time.sleep(
                        args.reconnect_delay
                    )
                    continue

                print(
                    "ESP32-CAM stream "
                    "reconnected."
                )

                continue

            now = time.monotonic()

            # ---------------------------------
            # Collect completed provider inference
            # ---------------------------------
            if (
                pending is not None
                and pending.done()
            ):
                try:
                    summary = pending.result()
                    result_frame_time = submitted_at
                except Exception as exc:
                    # Only expected hosted failures are recoverable here.
                    # Never print exception details that could contain credentials.
                    if not hosted:
                        raise
                    from detectors.roboflow_detector import DetectorUnavailableError
                    if not isinstance(exc, DetectorUnavailableError):
                        raise
                    summary = unavailable_summary(frame)
                    result_frame_time = None
                    print("AI provider unavailable; retrying on schedule.")
                pending = None
                if hosted and result_frame_time is not None and now - result_frame_time > stale_after:
                    summary = unavailable_summary(frame)
                    result_frame_time = None

                if last_completed is not None:
                    ai_fps = (
                        1.0
                        / max(
                            now - last_completed,
                            1e-9,
                        )
                    )

                last_completed = now

                if publisher.url:
                    publisher.offer(
                        summary,
                        camera_name,
                        now,
                    )

            if hosted and result_frame_time is not None and now - result_frame_time > stale_after:
                summary = unavailable_summary(frame)
                result_frame_time = None
                if publisher.url:
                    publisher.offer(summary, camera_name, now)

            # ---------------------------------
            # Start next provider inference
            # ---------------------------------
            if (
                pending is None
                and now >= next_inference
            ):
                submitted_at = now
                pending = executor.submit(
                    infer_detector,
                    detector,
                    frame.copy(),
                )

                next_inference = (
                    now
                    + 1.0 / args.fps
                )

            # ---------------------------------
            # Preview
            # ---------------------------------
            age = (
                now - last_completed
                if last_completed is not None
                else 0.0
            )

            display_frame = (
                frame.copy()
            )

            display_frame = draw_overlay(
                cv2,
                display_frame,
                summary,
                ai_fps,
                age,
            )

            cv2.imshow(
                "SmartPhset Live AI",
                display_frame,
            )

            if (
                cv2.waitKey(1) & 0xFF
                == ord("q")
            ):
                break

    except KeyboardInterrupt:
        print(
            "\nSmartPhset Live AI stopped."
        )

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
                try:
                    if executor is not None:
                        executor.shutdown(wait=True, cancel_futures=True)
                finally:
                    if detector is not None:
                        detector.close()


def parse_args(argv=None):

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument("--model-provider", choices=("local", "roboflow"), default="local")
    parser.add_argument("--roboflow-model-id", default="contamination-detection-ozkwx/1")
    parser.add_argument("--roboflow-api-url", default="https://serverless.roboflow.com")
    parser.add_argument("--imgsz", type=int, default=416)

    parser.add_argument(
        "--cam",
        type=int,
        default=0,
        help=(
            "local webcam index; "
            "default: 0"
        ),
    )

    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help=(
            "network video source, e.g. "
            "http://192.168.1.229:81/stream"
        ),
    )

    parser.add_argument(
        "--conf",
        type=float,
        default=0.4,
    )

    parser.add_argument(
        "--fps",
        type=float,
        default=5,
        help=(
            "maximum inference FPS; "
            "preview runs independently"
        ),
    )

    parser.add_argument(
        "--weights",
        default=DEFAULT_WEIGHTS,
    )

    parser.add_argument(
        "--device",
        default=None,
        help=(
            "optional Ultralytics device, "
            "e.g. cpu or 0"
        ),
    )

    parser.add_argument(
        "--backend-url",
        default=os.environ.get(
            "SMARTPHSET_BACKEND_URL"
        ),
        help=(
            "optional backend base URL; "
            "unset disables publishing"
        ),
    )

    parser.add_argument(
        "--publish-every",
        type=float,
        default=5,
        help=(
            "seconds between periodic "
            "backend snapshots"
        ),
    )

    parser.add_argument(
        "--reconnect-delay",
        type=float,
        default=2,
        help=(
            "seconds before reconnecting "
            "to a dropped network stream"
        ),
    )

    args = parser.parse_args(argv)
    if args.imgsz <= 0:
        parser.error("--imgsz must be greater than zero")
    if not args.roboflow_model_id.strip():
        parser.error("--roboflow-model-id must not be empty")
    from urllib.parse import urlsplit
    endpoint = urlsplit(args.roboflow_api_url)
    if (endpoint.scheme not in ("http", "https") or not endpoint.netloc
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment):
        parser.error("--roboflow-api-url must be HTTP(S) without credentials, query or fragment")

    if (
        not math.isfinite(
            args.publish_every
        )
        or args.publish_every <= 0
    ):
        parser.error(
            "--publish-every must be finite "
            "and greater than zero"
        )

    if (
        not math.isfinite(
            args.reconnect_delay
        )
        or args.reconnect_delay <= 0
    ):
        parser.error(
            "--reconnect-delay must be finite "
            "and greater than zero"
        )

    if args.backend_url:
        from urllib.parse import urlsplit

        parsed = urlsplit(
            args.backend_url
        )

        if (
            parsed.scheme
            not in ("http", "https")
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            parser.error(
                "--backend-url must be an "
                "HTTP(S) base URL without "
                "credentials, query or fragment"
            )

    if (
        not math.isfinite(args.fps)
        or args.fps <= 0
    ):
        parser.error(
            "--fps must be finite "
            "and greater than zero"
        )

    if (
        not math.isfinite(args.conf)
        or not 0 <= args.conf <= 1
    ):
        parser.error(
            "--conf must be between 0 and 1"
        )

    return args


def main():

    args = parse_args()

    try:
        run_camera(args)

    except (
        RuntimeError,
        OSError,
        ImportError,
        ValueError,
    ) as exc:

        raise SystemExit(
            f"SmartPhset Live AI: {exc}"
        ) from exc


if __name__ == "__main__":
    main()