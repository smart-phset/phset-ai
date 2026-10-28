# SmartPhset · AI

Persistent, authenticated mushroom-bag inference with the existing YOLO weights at
`models/best.pt`. Browser cameras upload sampled JPEGs; registered shared cameras
are opened by the worker and served as MJPEG. Video stays out of Spring/PostgreSQL.
Model outputs are suggestions requiring human inspection; this model has not been
validated on representative farm data. See [model card](docs/model-card.md).

[Frontend](https://github.com/smart-phset/phset-client) · [API](https://github.com/smart-phset/phset-api) · [Camera firmware](https://github.com/smart-phset/web-cam) · [Hardware](https://github.com/smart-phset/smart-things)

## Architecture and files

```text
session_service.py       persistent service, authenticated on 127.0.0.1:8002
live_camera.py           legacy single-source CLI/desktop or :8001 service
live_stream.py           shared latest-JPEG buffer and legacy HTTP streaming
backend_publisher.py     optional asynchronous Spring detection publishing
models/best.pt           tracked trained model; preserve it
 detectors/              local Ultralytics and optional hosted provider
bridge.py                separate image-upload service, default :8000
app.py / webcam.py       older interactive demos
requirements.txt         runtime pins
requirements-extra.txt   optional training/evaluation/Gradio tools
 tests/                  unittest suite, mocked cameras/inference
 docs/                   contracts, evaluation, model and legacy setup
```

`session_service.py` loads one `LocalUltralyticsDetector` for all sessions. A
nonblocking lock serializes inference: concurrent jobs receive 429 rather than
building an unbounded queue. Each browser session has its own random source ID
and results. Shared-source viewers share one capture worker and its latest frame;
AI runs while at least one session requests it. Shared detection results are
copied into analyzing sessions; video may contain worker-drawn boxes.

## Requirements and installation

Use Python **3.11**, Git and working camera/network permissions. CPU inference is
supported. `requirements.txt` pins torch 2.12.1, torchvision 0.27.1, Ultralytics
8.4.71, NumPy 2.3.5, opencv-python 4.10.0.84 and inference-sdk 1.7.3, with a
PyTorch CPU extra index. Do not replace the model to solve dependency problems.

```bash
# From the existing SmartPhset-AI checkout (remote: smart-phset/phset-ai)
python3.11 -m venv .venv       # first installation only; preserve an existing venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
```

Windows: `py -3.11 -m venv .venv`, then use
`.\.venv\Scripts\python.exe` for the commands. An existing uv-created environment
may lack pip; see [existing installation guidance](docs/live-camera.md).
Optional tooling: `python -m pip install -r requirements-extra.txt`.

## Configuration and startup

`.env.example` is a safe reference. Python does **not** load dotenv files;
export values into the service process explicitly. No keys belong in browser JS.

```bash
source .venv/bin/activate
export SMARTPHSET_AI_SERVICE_KEY='REPLACE_WITH_A_RANDOM_SECRET_OF_AT_LEAST_32_CHARACTERS'
export SMARTPHSET_CAMERA_SOURCES='{}'
python session_service.py
```

The entry point binds to **127.0.0.1:8002**; it has no host/port CLI options.
Replace the placeholder privately; use the identical key in Next's server env.
An empty `SMARTPHSET_CAMERA_SOURCES='{}'` is valid for browser-camera inference.
A browser-only session does not require a working Spring registry; shared-camera
listing and authorization do.

| Variable | Default / behavior |
|---|---|
| `SMARTPHSET_AI_SERVICE_KEY` | Required, at least 32 characters; bearer service authentication |
| `SMARTPHSET_CAMERA_SOURCES` | `{}`; JSON map of operator-selected IDs to URL or integer USB index 0–16 |
| `SMARTPHSET_WEIGHTS` | `models/best.pt` beside the code if blank/unset |
| `SMARTPHSET_CONFIDENCE` | `0.4`, local detector threshold |
| `SMARTPHSET_AI_MAX_SESSIONS` | 16; clamped to 1–64 |
| `OPENCV_IO_MAX_IMAGE_PIXELS` | Set to 921600 if not already set |
| `SMARTPHSET_BACKEND_URL` | Unset disables publishing; use permitted Spring origin |
| `SMARTPHSET_AI_INGEST_KEY` | Match Spring `AI_INGEST_KEY`; independent of service key |
| `BRIDGE_API_KEY` | Separate optional `bridge.py` authentication |
| `SMARTPHSET_LOG_DIR` | Optional bridge output directory |
| `ROBOFLOW_API_KEY` | Optional legacy hosted provider; persistent service uses local YOLO |

Shared-camera example, using the actual privately discovered LAN address:

```bash
export SMARTPHSET_CAMERA_SOURCES='{"esp32-cam":"http://CAMERA_LAN_IP:81/stream"}'
# Optional publishing, shared sources only:
export SMARTPHSET_BACKEND_URL='http://127.0.0.1:9090'
export SMARTPHSET_AI_INGEST_KEY='REPLACE_WITH_SPRING_INGEST_KEY'
python session_service.py
```

IDs must match Spring `SMARTPHSET_CAMERA_REGISTRY` exactly, e.g.
`esp32-cam=Grow room`. IDs accept 1–100 letters, digits, `_` and `-`; `browser` is
reserved. URLs accept HTTP, HTTPS or RTSP; URLs come exclusively from operator
configuration, never from viewer requests. Keep credentials/private URLs out of Git.

## Service contract and verification

Every request requires `Authorization: Bearer <service key>` and
`X-Camera-Owner: <64 lowercase hex characters>`. Next derives the owner from a
verified session cookie. Do not give this credential to users.

| Request | Behavior |
|---|---|
| `GET /sources` | Allowlisted shared-source status; does not open idle cameras |
| `POST /sessions` with `{"source_id":"browser"}` or shared ID | Create isolated session |
| `GET /sessions/{id}` | Status/result and heartbeat |
| `POST /sessions/{id}/start` or `/stop` with `{"revision":1}` | Newer positive revision enables/disables analysis |
| `POST /sessions/{id}/frames` | Browser-only JPEG; `X-Camera-Revision` must match current revision |
| `GET /sessions/{id}/stream` | Shared-source MJPEG |
| `DELETE /sessions/{id}` | Close one session |
| `DELETE /sessions` | Close this owner's sessions |

JPEG uploads must use `Content-Type: image/jpeg`, be at most **512 KiB**, at most
1280 on either dimension, and at most 921600 pixels. Sampling is at most 5 fps
per session. The HTTP server permits 32 concurrent handlers. Sessions expire after
60 seconds without heartbeat; a reaper checks every 2 seconds. A shared worker is
closed after its last session expires/closes, with no overlapping capture owner.
Stop with Ctrl+C/SIGTERM; shutdown waits up to 6 seconds for workers.

```bash
# Diagnostic owner only; the frontend normally supplies it.
owner=$(printf '%064d' 0)
curl --fail -H "Authorization: Bearer $SMARTPHSET_AI_SERVICE_KEY" \
  -H "X-Camera-Owner: $owner" http://127.0.0.1:8002/sources
python -m unittest discover -s tests -v
git diff --check
```

Ordinary tests mock hardware/model calls. The opt-in integration test uses
`SMARTPHSET_INTEGRATION_BACKEND_URL` and writes synthetic detections; run it only
against disposable infrastructure. Real model quality and devices need manual acceptance.
Publishing is best effort, without a durable queue. **Browser frame results are
returned to Next only**; the persistent service does not publish those to Spring.
Only shared-worker inference calls `BackendPublisher`.

## Legacy tools

`python live_camera.py --help` lists real options. The legacy process selects one
`--cam 0` or `--source URL`; `--serve --host 127.0.0.1 --port 8001` provides
`/health` and `/stream.mjpg`. It captures/infers continuously and is separate from
the on-demand session service. Avoid running both against the same physical camera.
Next retains `SMARTPHSET_AI_LIVE_BASE_URL` compatibility for older live routes.
`bridge.py` handles photo upload separately; see [bridge contract](docs/bridge-api.md).

## Troubleshooting and security

- Model loading: verify Python 3.11, installed pins and readable `models/best.pt`;
  check [model/evaluation docs](docs/evaluation.md). No claim of model accuracy follows from passing tests.
- Camera busy: close other owners, legacy scripts and meeting apps; one worker owns each configured shared source.
- Source unavailable / 503: verify camera power, raw LAN snapshot/stream and worker logs;
  network read failure retries, but an exited worker may require closing/reopening sessions.
- 401: service key mismatch or missing/invalid owner. Spring ingestion and registry use different keys.
- 404: expired/wrong-owner session or ID absent from worker/Spring allowlists.
- 429: session capacity, sampling limit or shared inference lock; reduce load and retry.
- 503: model/inference/capture failure or camera still stopping. Never interpret failure as a healthy crop.
- Keep the listener private. A container's `127.0.0.1` refers to itself; AWS cannot reach this laptop's loopback.
  Remote inference requires separately reviewed private connectivity and authenticated transport.

Do not publish camera ports, disable authentication, or commit environments, datasets,
private images or generated binaries. Review [contribution and licensing rules](CONTRIBUTING.md)
before making this repository public. Dataset/project attribution: Contamination
Detection by Oyster Mushroom Fruiting Bag, CC BY 4.0; see the model card. Preserve
Ultralytics licensing obligations and existing credits.
