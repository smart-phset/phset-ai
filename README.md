# SmartPhset AI

Mushroom-bag detection using local YOLO or an optional hosted Roboflow provider.
AI results are suggestions; this model has not been validated on representative
SmartPhset grow-room data. Confirm findings by inspecting the bag.

## Role in SmartPhset

Camera → Python/OpenCV → YOLO → annotated MJPEG →
[Next.js](https://github.com/smart-phset/phset-client/tree/feat/grow-room-monitoring).
Separately: AI result JSON → [Spring](https://github.com/smart-phset/phset-api)
→ PostgreSQL → frontend metadata/history. Video is not stored in Spring.
The [regular ESP32 repository](https://github.com/smart-phset/smart-things) contains
the MQTT controller. Camera source, private configuration and Linux/PowerShell
flashing instructions live in [web-cam](https://github.com/smart-phset/web-cam). The frontend README has the
[complete startup order](https://github.com/smart-phset/phset-client/blob/feat/grow-room-monitoring/README.md#start-smartphset-from-a-fresh-computerreboot).

`live_camera.py` handles live inputs; `live_stream.py` serves annotated MJPEG with
`--serve`. `bridge.py` is a separate photo-upload service (port 8000).
`app.py` is an optional Gradio demo; `webcam.py` is an older standalone demo.

## Requirements

Linux: Git, **Python 3.11**, its venv support, camera access; GUI libraries only
for desktop preview. The system Python may be newer: explicitly select 3.11.
Windows: Git for Windows, PowerShell, Python **3.11** with Python launcher `py`,
and camera access enabled in Windows privacy settings. WSL is not required.

`requirements.txt` pins torch 2.12.1, torchvision 0.27.1, ultralytics 8.4.71,
numpy 2.3.5, opencv-python 4.10.0.84 and inference-sdk 1.7.3, with the PyTorch
CPU extra index. GPU is not required. `requirements-extra.txt` adds optional
Gradio/training/evaluation packages; it is not required for live detection.
The inspected venv is Python 3.11.17. Windows runtime/hardware validation must
be performed on the teammate's machine; Linux success is not a Windows test.

## Clone

```text
git clone https://github.com/smart-phset/phset-ai.git
cd phset-ai
git switch feat/live-camera
```

Current live service work is on this feature branch, not necessarily main.
`models/best.pt` is tracked as a binary file, not a Git LFS pointer. Keep the
existing model; do not replace it just to resolve an environment problem.

## Configuration

No dotenv loader is used. Set variables in the AI terminal; `.env.example` is an
optional reference to copy to ignored `.env`. Copying it alone does not set the
environment. Do not commit real local values; commit only safe templates.

| Variable / option | Purpose / example | Secret? |
|---|---|---|
| SMARTPHSET_BACKEND_URL / --backend-url | Spring origin, `http://localhost:9090`; CLI wins; unset disables publishing | No |
| SMARTPHSET_AI_INGEST_KEY | Match Spring AI_INGEST_KEY, `YOUR_PRIVATE_AI_KEY` | Yes |
| ROBOFLOW_API_KEY | Required only with hosted provider; `YOUR_PRIVATE_KEY` | Yes |
| BRIDGE_API_KEY | Photo bridge auth; match frontend API_KEY | Yes |
| SMARTPHSET_WEIGHTS | Optional bridge weights path; default models/best.pt | No |
| SMARTPHSET_LOG_DIR | Optional bridge output directory; default bridge_log | No |
| --cam | Local webcam index, `0` | No |
| --source | Network MJPEG URL, `http://YOUR_ESP32_CAM_IP:81/stream`; overrides --cam | No |
| --model-provider | `local` default, or `roboflow` | No |
| --weights | Live local model file, defaults to models/best.pt beside script | No |
| --device | Optional inference device, e.g. `cpu` | No |
| --conf / --imgsz / --fps | Confidence threshold 0.4 / input size 416 / requested inference rate 5 | No |
| --publish-every | Periodic snapshot interval, 5 seconds; verdict changes also publish | No |
| --reconnect-delay | Desktop network read retry delay, 2 seconds | No |
| --serve / --host / --port | Headless HTTP service, 127.0.0.1:8001 by default | No |
| --roboflow-model-id | Hosted default contamination-detection-ozkwx/1 | No |
| --roboflow-api-url | Hosted default https://serverless.roboflow.com | No |

The local provider needs no hosted key. Hosted mode sends selected frames to
Roboflow and may incur usage charges; no silent local fallback occurs. Full option
help: `python live_camera.py --help` and `python bridge.py --help`.

Camera IDs are derived from input: `--cam 0` → `webcam-0`; a `--source` stream →
`esp32-cam`. Set frontend SMARTPHSET_AI_CAMERA_ID accordingly for Overview/history.
The current frontend Live Detection metadata route is hard-coded to webcam-0:
ESP32 video can work while that panel shows webcam metadata. Verify ESP32 metadata
via Overview/history or Spring `?camera=esp32-cam` instead.

## Linux setup

One time, with `python` resolving to Python 3.11 (use `python3.11` instead if needed):

```bash
python --version
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
# Optional private configuration reference:
cp .env.example .env
```

Existing developer venv was created with uv and may not contain pip. Reuse it;
do not recreate it. The existing uv install route is documented in
[docs/live-camera.md](docs/live-camera.md), including its CPU index behavior.

Each session:

```bash
source .venv/bin/activate
export SMARTPHSET_BACKEND_URL="http://localhost:9090"
export SMARTPHSET_AI_INGEST_KEY="YOUR_PRIVATE_AI_KEY"
python live_camera.py --cam 0 --model-provider local --device cpu --conf 0.4 --fps 5 --publish-every 5 --serve --host 127.0.0.1 --port 8001
```

Replace the key privately with Spring's AI_INGEST_KEY before running. For ESP32-CAM,
stop the first process and use (replace the camera IP):

```bash
python live_camera.py --source "http://YOUR_ESP32_CAM_IP:81/stream" --model-provider local --device cpu --conf 0.4 --fps 5 --publish-every 5 --serve --host 127.0.0.1 --port 8001
```

## Windows setup

One time: `py --list` shows installed interpreters. If default `py` is 3.11,
`py -m venv .venv` works; explicitly choosing it avoids using another version:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
Copy-Item .env.example .env
```

If activation is blocked, either use `.\.venv\Scripts\python.exe` directly in
place of `python`, or permit locally created scripts for **this process**:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Do not change machine-wide security policy. Organization policy may override this;
using the venv executable directly does not require activation.

Each session (replace the key privately):

```powershell
.\.venv\Scripts\Activate.ps1
$env:SMARTPHSET_BACKEND_URL = "http://localhost:9090"
$env:SMARTPHSET_AI_INGEST_KEY = "YOUR_PRIVATE_AI_KEY"
python live_camera.py --cam 0 --model-provider local --device cpu --conf 0.4 --fps 5 --publish-every 5 --serve --host 127.0.0.1 --port 8001
```

For ESP32-CAM, stop that process and select the stream instead:

```powershell
python live_camera.py --source "http://YOUR_ESP32_CAM_IP:81/stream" --model-provider local --device cpu --conf 0.4 --fps 5 --publish-every 5 --serve --host 127.0.0.1 --port 8001
```

## Running

The commands above serve live frames without a desktop window. Open
http://127.0.0.1:8001/health and http://127.0.0.1:8001/stream.mjpg.
Point frontend SMARTPHSET_AI_LIVE_BASE_URL to http://127.0.0.1:8001.
Stop with Ctrl+C before selecting another source; only one process can own the port.

For a desktop preview, omit `--serve`. **QT_QPA_PLATFORM=xcb is Linux/X11-specific**;
it is not needed for the headless service and must not be set on Windows.

Linux/X11 preview:

```bash
QT_QPA_PLATFORM=xcb python live_camera.py --cam 0 --model-provider local --device cpu
```

Windows preview:

```powershell
python live_camera.py --cam 0 --model-provider local --device cpu
```

Press q in the desktop window or Ctrl+C in the terminal to stop.

### Upload Image service (optional, separate terminal)

Activate the same venv in another terminal. Use a separate private bridge key:

```bash
export BRIDGE_API_KEY="YOUR_PRIVATE_BRIDGE_KEY"
python bridge.py --host 127.0.0.1 --port 8000
```

```powershell
$env:BRIDGE_API_KEY = "YOUR_PRIVATE_BRIDGE_KEY"
python bridge.py --host 127.0.0.1 --port 8000
```

Set frontend BACKEND_MODE=bridge, BACKEND_URL=http://127.0.0.1:8000, and API_KEY
matching BRIDGE_API_KEY; restart Next. This uploads images to `/image`; it does not
publish live snapshots to Spring. Do not start the bridge on 8001 while live is running.

## Testing

From an activated venv, these work on both platforms:

```text
python -m unittest discover -s tests -v
python live_camera.py --help
python tools/evaluate_detector.py --help
git diff --check
```

Tests mock cameras and hosted requests; the opt-in backend integration test needs
a running configured backend and SMARTPHSET_INTEGRATION_BACKEND_URL (see its test
file); it writes uniquely named synthetic records. No real hosted key is needed
for the ordinary suite. Dependency checks are separate from model-quality validation.

Linux live checks:

```bash
curl http://127.0.0.1:8001/health
curl 'http://localhost:9090/api/ai/detections/latest?camera=webcam-0'
curl -H "Authorization: Bearer $BRIDGE_API_KEY" http://127.0.0.1:8000/status
```

PowerShell live checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod 'http://localhost:9090/api/ai/detections/latest?camera=webcam-0'
Invoke-RestMethod -Headers @{ Authorization = "Bearer $env:BRIDGE_API_KEY" } -Uri http://127.0.0.1:8000/status
```

Check `streaming: true`, moving frames in the browser, and advancing capture times
in Spring. Use camera=esp32-cam when testing the network source. Upload a JPEG/PNG
from `/scan` with bridge mode configured. Camera availability and detection quality
require real hardware checks; unit tests cannot prove either.

## Common problems

- Webcam in use: close video meetings, browser camera capture and other Python
  preview processes; select the correct --cam index and enable OS camera permissions.
- Port 8001 in use: stop the previous service. Linux: `ss -ltnp 'sport = :8001'`.
  PowerShell: `Get-NetTCPConnection -LocalPort 8001 -State Listen`, then inspect
  `Get-Process -Id <OwningProcess>` before `Stop-Process -Id <OwningProcess>`.
- Backend unavailable: video may still work. Check Spring on 9090 and backend URL;
  failed publishes are dropped, not durably queued. New eligible results resume publishing.
- Wrong AI ingestion key: Spring returns 401. SMARTPHSET_AI_INGEST_KEY must equal
  Spring AI_INGEST_KEY; the IoT and bridge keys do not substitute for it.
- Stale detections: check capture time, camera ID, publishing enablement and key.
  Camera/inference failure is GREY, never healthy. Current live panel metadata
  selects webcam-0 even when viewing an ESP32 stream.
- ESP32 URL unreachable: obtain current board IP from serial/router; use port 81
  `/stream`, not laptop IP or `/capture`. Verify common network, no client isolation,
  stable camera power and raw stream in a browser first.
- Serving mode reports camera_unavailable: restore camera/network and restart
  Python. Desktop network mode has reconnect behavior; do not assume serving mode
  automatically recovers every camera failure.
- Missing model/dependencies: run from the clone root, verify models/best.pt and
  active Python 3.11. Do not install multiple OpenCV distributions sharing cv2.
  Preserve pinned versions; inspect pip errors and network/index access first.
- Linux Qt plugin error in desktop preview: use a working X11/XWayland session
  and required GUI libraries. Do not copy Linux xcb settings into Windows.

More: [live options/providers](docs/live-camera.md), [MJPEG design](docs/mjpeg-live.md),
[model card](docs/model-card.md), [evaluation](docs/evaluation.md),
[photo bridge contract](docs/bridge-api.md).

## Git workflow

Start with a clean worktree (`git status`). Update the branch named in Clone before
creating your own feature branch. These commands work in Bash and PowerShell:

```text
git pull --ff-only
git switch -c feat/my-change
# Edit and run the checks above.
git status
git add README.md
# Add other intended files explicitly; never add private configuration.
git diff --cached
git commit -m "Describe the change"
git push -u origin feat/my-change
```

Open a Pull Request against the team's agreed integration branch. Do not push
teammate changes directly to main. Never use `git push --force` unless the team
explicitly agrees and understands why. If pull refuses, inspect local changes and
coordinate; do not discard work with a hard reset.

## Security notes

Never commit `.env`, `.env.local`, private `config.h`, Wi-Fi passwords, API keys,
DB passwords or auth secrets. Commit only safe example files. Inspect
`git diff --cached` before each commit; do not force-add ignored files. If a secret
was committed, rotate it and coordinate cleanup; deleting it does not revoke it.

## Credits and contributing

Hosted model/project: **Contamination Detection** by **Oyster Mushroom Fruiting
Bag**, [Roboflow Universe](https://universe.roboflow.com/oyster-mushroom-fruiting-bag/contamination-detection-ozkwx),
project license CC BY 4.0. Published project metrics are not local farm validation.
Ultralytics licensing is described by its
[official license page](https://www.ultralytics.com/license); consult the applicable
terms for your deployment. See [CONTRIBUTING.md](CONTRIBUTING.md) for repository
conventions and protected files.
