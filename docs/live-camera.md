# SmartPhset desktop live camera

Run from your existing repository. Uses `models/best.pt` without modifying or
retraining it. Point at oyster mushroom bags; this demo model is not field validated.

## Arch Linux environment

Use a local graphical desktop session with access to `/dev/video*`, rather than a
headless server or SSH session. Use **Python 3.11**, as specified by this repository's
pinned requirements; Arch's default Python can be newer. Install Python 3.11 using
your existing Python version manager first if `python3.11` is unavailable.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
# Clear conflicting OpenCV distributions in an existing venv (safe in a fresh one).
python -m pip uninstall -y opencv-python-headless opencv-python opencv-contrib-python opencv-contrib-python-headless
python -m pip install -r requirements.txt
python -m pip check
```

`requirements.txt` now selects `opencv-python==4.10.0.84`, the GUI build, instead of
headless OpenCV. Do not install both: they share the `cv2` namespace. This also enables
the existing `webcam.py`; the bridge still uses the same OpenCV decoding APIs.
On Arch, if GUI/shared-library startup reports missing X11, GL or Qt xcb libraries:

```bash
sudo pacman -S --needed mesa libglvnd libx11 libxcb libxext libxrender libsm libice libxkbcommon-x11 xcb-util-cursor xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm
```

Check GUI support and camera device permissions:

```bash
python -c 'import cv2; print(cv2.getBuildInformation())'
ls -l /dev/video*
```

The OpenCV build should list GUI support. If camera access is denied, check your
desktop session's device ACLs/group permissions and close applications using the
camera. If a Wayland session reports Qt platform errors, try XWayland with
`QT_QPA_PLATFORM=xcb python live_camera.py` (XWayland must be installed and running).

## Run

```bash
python live_camera.py
python live_camera.py --cam 0
python live_camera.py --cam 1
python live_camera.py --cam 0 --conf 0.4 --fps 5
python live_camera.py --device cpu
python live_camera.py --weights models/best.pt
```

`--cam` defaults to 0, `--conf` to 0.4, `--fps` to 5. Default weights resolve to
`models/best.pt` beside the script, independently of the shell's working directory.
Device selection is left to Ultralytics unless `--device` is supplied; CUDA is not
required. Input inference size is 416, matching the bridge.

A single worker loads YOLO once and predicts on copied OpenCV frames. The main thread
continues reading and displaying frames while inference runs. At most one inference
is in flight, with no queue of old frames. `--fps` limits inference starts; actual AI
FPS depends on hardware. The overlay shows measured completion FPS and inference
latency, plus the latest result's age. Bounding boxes remain visible between passes;
they come from the last inspected frame and can lag moving bags.

The class-name contamination prefix and contamination-first verdict follow
`bridge.py`; only labels starting with `healthy` count as healthy in this preview.
Unrelated labels never produce a healthy verdict. The bridge and `POST /image`
are unchanged.

| Situation | Verdict/message | Level |
|---|---|---|
| Contaminated confidence >= 0.80 | `contamination_suspected` / Possible contamination | RED |
| Contaminated confidence >= 0.40 and < 0.80 | `contamination_suspected` / Possible contamination | AMBER |
| Healthy bags only | `no_contamination_seen` / No contamination seen | GREEN |
| No relevant detections, including before first inference | `no_detection` / Could not inspect | GREY |

Severity always uses `max_contaminated_conf`, never overall `max_conf`. If you lower
`--conf` below 0.40, lower-confidence contamination still gives Possible contamination
with GREY (below the defined alert threshold), never GREEN.

Press **q** with the preview focused or **Ctrl+C** in the terminal. Camera read errors
stop inspection instead of continuing to show a healthy result. `finally` releases
the camera and destroys all windows on normal exit, interruption, or exceptions.
Shutdown waits for any current inference to finish after releasing GUI resources.

## Hardware-independent checks

```bash
python -m py_compile live_camera.py
python -m unittest discover -s tests -v
```

Tests use the standard library and mocked camera/model objects; they require neither
OpenCV, torch, a display nor a webcam. They verify verdict thresholds, mixed healthy
and contaminated confidence, unknown/empty results, prediction settings, cleanup, and
preview progress while inference is pending. Real camera capture, GUI startup, and
model latency must also be checked on your laptop with the run commands above.

## Publish detection snapshots to Spring Boot

On this Arch/Hyprland machine the OpenCV Qt window currently requires
`QT_QPA_PLATFORM=xcb`.

```bash
cd /home/ratanak/smart-phset/SmartPhset-AI
source .venv/bin/activate
QT_QPA_PLATFORM=xcb python live_camera.py \
  --cam 0 \
  --conf 0.4 \
  --fps 5 \
  --backend-url http://localhost:9090 \
  --publish-every 5
```

Alternatively, `SMARTPHSET_BACKEND_URL=http://localhost:9090` sets the default
backend URL. Without a URL, publishing is disabled and no network worker starts.
If the backend configures `AI_INGEST_KEY`, set the same private value in the AI shell:

```bash
export SMARTPHSET_AI_INGEST_KEY='<your-local-key>'
```

The publisher POSTs JSON to `/api/ai/detections` with `Content-Type: application/json`
and the optional `X-SmartPhset-AI-Key` header. Each queued snapshot has a new UUID
`event_id`, camera ID `webcam-<cam>`, UTC capture timestamp, verdict, severity,
counts, both confidence maxima, source dimensions, inference milliseconds and boxes
(`label`, `conf`, integer `xyxy`). No frames or video are sent, and no extra inference
runs. The capture timestamp is taken at inference start rather than HTTP send time.

The first completed inference publishes immediately. Later completed results publish
at most every five seconds by default, or immediately when verdict/severity changes.
No snapshots publish before the first completed inference. Publishing continues only
with completed inference results so a stalled inference cannot repeatedly report an
old healthy observation as new.

A single daemon HTTP worker has one in-flight request and at most one pending event.
New eligible snapshots replace the pending event, keeping memory bounded during
outages. Under a slow backend, intermediate state transitions can be superseded by
the newest snapshot. HTTP uses the Python standard library with a three-second socket
timeout. Connection failures, timeouts and HTTP errors log a warning and drop that
event; future periodic/change events continue without retries or durable buffering.
Capture, preview, YOLO and q handling never wait for networking. Shutdown discards
pending publishing work without waiting for an HTTP request.

Verify persistence from another terminal:

```bash
curl 'http://localhost:9090/api/ai/detections/latest?camera=webcam-0'
curl 'http://localhost:9090/api/ai/detections?camera=webcam-0&limit=20'
```

Publisher tests mock HTTP and use no backend, webcam or model. Existing cleanup tests
remain part of `python -m unittest discover -s tests -v`. `bridge.py` and its existing
`POST /image` API are unchanged.
