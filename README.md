# SmartPhset AI

Mushroom-bag detection for SmartPhset using a local Ultralytics model or the
existing Roboflow mushroom detector. AI checks are suggestions, not proof of
health: no representative SmartPhset grow-room validation has been completed.

`live_camera.py` reads a webcam or ESP32-CAM stream, schedules one inference at a
time, applies the shared contamination-first verdict policy and displays results.
It optionally publishes structured detection snapshots to Spring; it never sends
video to the backend. Hosted inference sends selected frames to Roboflow.

## Start here

Use Python 3.11 and the existing uv workflow. Full setup, dependency/index
explanation, GUI troubleshooting and manual checks are in
[the live-camera guide](docs/live-camera.md).

```bash
uv venv --python 3.11 .venv  # fresh checkout only; reuse an existing environment
UV_CACHE_DIR=/tmp/smartphset-uv-cache uv pip install \
  --python .venv/bin/python --index-strategy unsafe-best-match -r requirements.txt
UV_CACHE_DIR=/tmp/smartphset-uv-cache uv pip check --python .venv/bin/python
source .venv/bin/activate
QT_QPA_PLATFORM=xcb python live_camera.py \
  --cam 0 --model-provider local --conf 0.4 --fps 5
```

The index strategy is specific to this repository's PyTorch CPU extra-index
setup; it is not a general installation recommendation. See the guide before
changing dependencies. Windows uses `.venv\Scripts\python.exe` and PowerShell
activation; Linux GUI examples use xcb where required.

Local is the default and uses `models/best.pt` without requiring a hosted key.
For ESP32 use `--source "http://<esp32-ip>:81/stream"`. For hosted detection:

```bash
export ROBOFLOW_API_KEY="..."  # private environment value, never commit it
QT_QPA_PLATFORM=xcb python live_camera.py \
  --source "http://<esp32-ip>:81/stream" --model-provider roboflow --fps 1
```

Hosted model defaults to `contamination-detection-ozkwx/1`; calls may consume paid
usage. Expected hosted failures keep preview alive and become GREY / Could not
inspect. There is no silent fallback. q or Ctrl+C exits with resource cleanup.

## Guides and entry points

| Path | Purpose |
| --- | --- |
| [docs/live-camera.md](docs/live-camera.md) | Setup, provider CLI, webcam/ESP32, backend, security, failure behavior and manual checklist |
| [docs/model-integration.md](docs/model-integration.md) | Architecture, hosted model attribution, actual SDK implementation and validation limits |
| [docs/evaluation.md](docs/evaluation.md) | Repeatable labeled-image comparison, scoring rules, CSV and latency metrics |
| `tools/evaluate_detector.py` | Sequential evaluation through the shared detector abstraction |
| `bridge.py` | Existing photo/telemetry/status server; see [bridge guide](docs/run-the-bridge.md) |
| `webcam.py`, `app.py` | Existing standalone demos; app requires optional requirements |
| `models/best.pt` | Preserved local weights; [local model card](docs/model-card.md) |
| `training/`, `evidence/` | Historical training/public-data evaluation; [training guide](docs/training.md) |
| `CODEX_WORK_LOG.md` | Permanent phase, research, validation and resume history |

The live severity policy is RED at contamination >=0.80, AMBER at >=0.40 and
<0.80, GREY below 0.40/no recognized detection/unavailable/expired hosted result,
and GREEN only for Healthy detections without contamination. Contamination wins.
Messages are Possible contamination, No contamination seen, and Could not inspect.
The live policy does not relabel the separate legacy bridge/frontend wording.

## Evaluate and validate

```bash
python tools/evaluate_detector.py --dataset evaluation \
  --model-provider local --output evaluation-results-local.csv
python -m unittest discover -s tests -v
python live_camera.py --help
python tools/evaluate_detector.py --help
```

Create `evaluation/healthy/`, `evaluation/contaminated/`, and `evaluation/negative/`
with your own labeled images first. CSV files are ignored by Git. Review
contamination misses, false alerts and unavailable inspections alongside accuracy.
No real SmartPhset evaluation dataset/results currently exist in this repository.
Tests use mocked hosted requests; no real API key, camera or running backend is
required, but the installed requirements are needed for the full suite.

Never commit ROBOFLOW_API_KEY, SMARTPHSET_AI_INGEST_KEY or bridge keys. Backend
publishing uses SMARTPHSET_BACKEND_URL / --backend-url and the optional ingest key
from the environment; details are in the live guide. The bridge keeps its own
BRIDGE_API_KEY configuration; see its guide before exposing it.

## Credits and contributing

Hosted model/project: **Contamination Detection** by **Oyster Mushroom Fruiting
Bag**, [Roboflow Universe](https://universe.roboflow.com/oyster-mushroom-fruiting-bag/contamination-detection-ozkwx),
project license CC BY 4.0. Published project metrics are not local farm validation.
Ultralytics licensing is described by its
[official license page](https://www.ultralytics.com/license); consult the applicable
terms for your deployment. See [CONTRIBUTING.md](CONTRIBUTING.md) for repository
conventions and protected files.
