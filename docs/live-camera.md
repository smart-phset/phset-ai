# SmartPhset live camera

Run from the repository root in a graphical desktop session. Webcam and ESP32
streams use the same detector/verdict/backend pipeline. The local model is the
default; neither provider is validated on representative SmartPhset grow-room data.

## Python 3.11 setup with uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first.
For a fresh Linux environment:

```bash
uv venv --python 3.11 .venv
UV_CACHE_DIR=/tmp/smartphset-uv-cache \
uv pip install \
  --python .venv/bin/python \
  --index-strategy unsafe-best-match \
  -r requirements.txt
UV_CACHE_DIR=/tmp/smartphset-uv-cache uv pip check --python .venv/bin/python
source .venv/bin/activate
```

Reuse an existing `.venv`; do not recreate it merely because it lacks pip. uv
installs directly into the selected Python environment. On Windows, use
`.venv\Scripts\python.exe` for `--python` and activate with
`.\.venv\Scripts\Activate.ps1`; set environment variables using PowerShell syntax.

The verified Linux stack is Python 3.11, inference-sdk 1.7.3, NumPy 2.3.5,
requests 2.34.2, Ultralytics 8.4.71, torch 2.12.1+cpu,
torchvision 0.27.1+cpu and opencv-python 4.10.0.84. requests is an SDK-resolved
transitive dependency, not an exact pin in requirements.txt. This requirements
file is not a complete transitive lockfile.

This repository includes the PyTorch CPU extra index. uv's default `first-index`
policy can restrict shared packages to versions from that index, excluding the
PyPI versions required by the SDK. The command above was used successfully for
this combined environment; `unsafe-best-match` considers both indexes. It is a
workaround for this setup, not a universal recommendation: it relaxes index
isolation and carries dependency-confusion risk. See [uv index behavior](https://docs.astral.sh/uv/concepts/indexes/#searching-across-multiple-indexes).
NumPy was reduced from 2.4.4 because SDK 1.7.3 requires <2.4; requests increased
from 2.28.1 because it requires >=2.33. Ultralytics/torch/torchvision/OpenCV were
preserved. Do not solve installation failures by blindly upgrading this stack.

Use GUI-enabled `opencv-python`, not a simultaneous headless/contrib distribution
sharing the `cv2` namespace. Check `python -c 'import cv2; print(cv2.getBuildInformation())'`
and camera device permissions if startup fails. On Linux, ensure a working
X11/XWayland desktop and the GUI libraries named by any loader error. The examples
use `QT_QPA_PLATFORM=xcb` for the tested desktop setup; other platforms may omit it.

## Local provider

```bash
QT_QPA_PLATFORM=xcb python live_camera.py \
  --cam 0 --model-provider local --conf 0.4 --fps 5

QT_QPA_PLATFORM=xcb python live_camera.py \
  --source "http://<esp32-ip>:81/stream" \
  --model-provider local --conf 0.4 --fps 5
```

Replace `<esp32-ip>` before running. The ESP32 firmware typically exposes
`http://<esp32-ip>/`, `/capture`, and port 81 `/stream`. Confirm these endpoints
for your firmware. ESP32 supplies images/video; AI runs on the laptop/server/edge
device. Webcam uses `--cam` (default 0); `--source` takes precedence when supplied.
Network snapshots are for inspection; use the MJPEG stream URL for live preview.

Default weights resolve to `models/best.pt` beside the script. `--weights` selects
another existing local file, `--imgsz` defaults to 416, and `--device` optionally
selects e.g. `cpu` or `0`. YOLO loads once; no API key or hosted SDK runtime is
needed for the local path. Device selection otherwise remains with Ultralytics.

## Roboflow provider

```bash
export ROBOFLOW_API_KEY="..."
QT_QPA_PLATFORM=xcb python live_camera.py \
  --source "http://<esp32-ip>:81/stream" \
  --model-provider roboflow \
  --roboflow-model-id contamination-detection-ozkwx/1 \
  --roboflow-api-url https://serverless.roboflow.com \
  --conf 0.4 --fps 1
```

Set your actual key privately; `...` is only a placeholder. Hosted inference
sends selected image frames to Roboflow and may incur usage charges. Start with
1 requested inference FPS rather than the incoming video rate; network latency,
quota and usage cost differ from local inference. Preview runs independently.
Default requested FPS remains 5 for both providers unless explicitly overridden.
No live hosted request is made by automated tests.

Missing `ROBOFLOW_API_KEY` fails startup clearly. Hosted mode does not load local
weights. There is no automatic fallback to local. See [model and SDK details](model-integration.md).

## Scheduling, verdicts and failures

One worker handles at most one inference in flight. Busy frames are dropped,
not queued. `--fps` limits inference starts; it does not set video FPS or guarantee
completion frequency. A frame copy isolates inference from overlay drawing.
The overlay shows completion FPS, provider latency and time since the most recent
completion. Boxes refer to the inspected frame and can lag motion.

| Result | Severity | Message |
| --- | --- | --- |
| Contamination confidence >= 0.80 | RED | Possible contamination |
| Contamination confidence >= 0.40 and < 0.80 | AMBER | Possible contamination |
| Contamination confidence < 0.40 | GREY | Possible contamination |
| Healthy detection(s), no contamination | GREEN | No contamination seen |
| No recognized detections, unavailable or expired hosted result | GREY | Could not inspect |

Contamination always wins over Healthy, even below 0.40. Confidence stays
unrounded internally. `--conf` filters provider detections independently of these
fixed severity rules; lowering it can expose low-confidence GREY contamination.
Only recognized Healthy labels can produce GREEN; unrelated labels cannot.

Camera failures and inference failures are separate:

- Network read failure releases/reopens the stream after `--reconnect-delay`
  (default 2 seconds). Failed reconnects are retried. An initial open failure
  stops startup. A local webcam read failure stops inspection.
- Expected hosted/API failure keeps preview alive, replaces results with GREY /
  Could not inspect, and retries at later scheduled opportunities. It does not
  reconnect the camera. No SDK exception text or key is printed.
- Hosted results expire after `max(5 seconds, 2 / requested FPS)` from frame
  submission, including results already too old when they arrive. Expiry clears
  boxes and offers GREY to the publisher. Local result persistence is unchanged.
- Unexpected programming errors and local inference errors still stop the process.

Press **q** with preview focused, or **Ctrl+C** in the terminal. Cleanup closes
the publisher, releases the camera, destroys windows, shuts down the worker and
closes the detector. Shutdown waits for active inference; hosted network awaits
have an eight-second provider deadline. Synchronous encoding or blocking camera
operations are not preemptible; q is processed when preview advances, so use
Ctrl+C during reconnect waits.

## Publish detection snapshots to Spring Boot

```bash
export SMARTPHSET_BACKEND_URL="http://localhost:9090"
export SMARTPHSET_AI_INGEST_KEY="..."  # only if your backend requires it
QT_QPA_PLATFORM=xcb python live_camera.py \
  --source "http://<esp32-ip>:81/stream" \
  --model-provider local --conf 0.4 --fps 5 \
  --backend-url http://localhost:9090 --publish-every 5
```

CLI `--backend-url` overrides the environment default. Without either, publishing
is disabled. `SMARTPHSET_AI_INGEST_KEY` supplies the optional
`X-SmartPhset-AI-Key` header; configure the matching value on your backend.

Publisher POSTs JSON to `/api/ai/detections`. Fields remain `event_id` (UUID),
`camera_id` (`webcam-<cam>` or `esp32-cam`), `captured_at` (UTC), `verdict`,
`severity`, `message`, `n_contaminated`, `n_healthy`, `max_conf`,
`max_contaminated_conf`, `width`, `height`, `inference_ms`, and `boxes`
(`label`, `conf`, integer `xyxy`). Inference milliseconds are rounded for the
payload; confidence is not. Successful capture timestamps are taken at inference
start. Unavailable/expiry snapshots have a current snapshot timestamp, empty boxes
and zero latency/counts; they are not successful observations.

Spring receives structured snapshots, never image/video data. First completed
inspection (including an unavailable result) is offered immediately; subsequent
results are eligible every `--publish-every` seconds (default 5) or when
verdict/severity changes. Hosted expiry also offers GREY; no pre-inference healthy
snapshot is invented. Publisher has one HTTP request and one replaceable pending
snapshot, with a three-second socket timeout. Errors are best effort: failed events
are dropped, no durable queue/retry; later eligible snapshots continue. Backend
outages do not block preview/inference. Shutdown drops pending publishing work.
The Spring backend is unchanged by this integration.

## Security and recovery

Keep ROBOFLOW_API_KEY and SMARTPHSET_AI_INGEST_KEY in the environment, never source,
CLI key arguments or committed files. `.env` and CSV files are ignored; do not
force-add secrets. Avoid logging keys, request headers, or raw SDK exception text.
Tests/examples use placeholders only. Prefer credential-free stream/API URLs;
stream source URLs are printed at startup.

If package downloads or Git pushes fail DNS, restore access in the affected
terminal/environment. Do not recreate completed code or install pip into `.venv`.
Inspect `git status`, branch and work log before resuming; an external successful
push can be reconciled into the next normal checkpoint without a log-only commit.

## Automated and manual validation

```bash
python -m unittest discover -s tests -v
python live_camera.py --help
python tools/evaluate_detector.py --help
UV_CACHE_DIR=/tmp/smartphset-uv-cache uv pip check --python .venv/bin/python
```

Full tests need installed requirements (including NumPy/SDK/OpenCV for installed-API
and decode fixtures), but need no real key, camera, display or running backend.
Roboflow/HTTP inference tests are mocked. See [evaluation](evaluation.md) for
labeled-image comparison; current project has no real SmartPhset evaluation results.

Manual checks still required on your equipment:

- [ ] Open ESP32 root/capture/stream endpoints and verify live frames.
- [ ] Run local webcam and ESP32 commands; check responsive preview and overlay.
- [ ] Enable backend publishing; verify latest/history snapshots in the running
  backend for `camera=esp32-cam` (or `webcam-0`), correct fields and state changes.
- [ ] Start hosted provider with private environment key, explicitly accepting
  hosted usage; verify box alignment and expected verdicts.
- [ ] Temporarily interrupt hosted connectivity while camera remains reachable:
  preview continues, becomes GREY, no ESP32 reconnect; restore and verify recovery.
- [ ] Interrupt camera stream separately and verify reconnect after restoration.
- [ ] Run both evaluator commands on independently labeled representative images;
  inspect misses, false alerts, availability and latency—not accuracy alone.
- [ ] Verify q and Ctrl+C cleanup, including a slow inference/reconnect case.

No live hosted, hardware GUI/ESP32 or running-backend acceptance is claimed by the
automated validation. A synthetic local inference smoke test is not model-quality
validation.
