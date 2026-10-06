# SmartPhset AI

The mould-detection AI for SmartPhset, the oyster-mushroom climate and contamination system. A photo of a grow
bag goes in; the AI marks bags it thinks are contaminated, with a confidence score.

- **`bridge.py`** is the AI server. The website and the Node backend send photos to it (`POST /image`).
- **`models/best.pt`** is the trained model: YOLOv8n, 6 MB, runs on an ordinary laptop CPU in well under a second.
- The website is a separate repo: [SmartPhset-Prototype-Frontend](https://github.com/menghoutishere-code/SmartPhset-Prototype-Frontend)
  (live at https://smartphset.vercel.app).

> **AI checks are suggestions, not proof.** The model learned from public photos and is **not yet validated on a
> real farm**. "Could not check" never means healthy.

## Quick start (Windows, Python 3.11)

```powershell
git clone git@github.com:menghoutishere-code/SmartPhset-AI.git
cd SmartPhset-AI
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # a few hundred MB, mostly torch (CPU build)

$env:BRIDGE_API_KEY = "<pick a long random key>"
python bridge.py --api-key $env:BRIDGE_API_KEY
```

Then open `http://localhost:8000/?key=<your key>` in a browser. The page has an upload box to test a photo.
On macOS or Linux use `python3.11 -m venv .venv`, `source .venv/bin/activate` and `export BRIDGE_API_KEY=...`.

Test from the command line with one of the sample photos:

```bash
curl -s -H "Authorization: Bearer <your key>" -H "Content-Type: image/jpeg" \
  --data-binary @evidence/demo/image0.jpg "http://localhost:8000/image?camera=test"
```

**Next:** [docs/run-the-bridge.md](docs/run-the-bridge.md) covers the tunnel and connecting the website or the
backend.

## What is in here

| Path | What it is |
|---|---|
| `bridge.py` | The AI server: `/image` (photo in, result out), `/telemetry`, `/status`, and a status page |
| `models/best.pt` | The trained model (see [docs/model-card.md](docs/model-card.md)) |
| `app.py` | A simple browser test page (Gradio). Needs `requirements-extra.txt` |
| `webcam.py` | Runs the model live on a webcam window |
| `training/` | Scripts to retrain and evaluate the model (see [docs/training.md](docs/training.md)) |
| `evidence/` | Accuracy charts, the evaluation report and the threshold check behind the alert levels |
| `docs/` | How to run it, the API, the model card, retraining |

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `--api-key` or `BRIDGE_API_KEY` | none | Every request must send `Authorization: Bearer <key>` (or `?key=`). **Always set it before exposing the bridge through a tunnel.** |
| `--weights` or `SMARTPHSET_WEIGHTS` | `models/best.pt` | The model file |
| `--log` or `SMARTPHSET_LOG_DIR` | `bridge_log/` | Where CSV logs and the checked photos are saved |
| `--port` | `8000` | Port |
| `--conf` | `0.4` | Lowest confidence the model reports (the amber level) |

`python bridge.py --help` lists the camera polling options too.

## Alert levels (used by the website)

Only the highest **contaminated** box counts (`max_contaminated_conf`):

| Level | Rule | Shown as |
|---|---|---|
| Red | 0.80 or more | Likely mould |
| Amber | 0.40 to 0.79 | Please check this bag |
| Green | Bags found, nothing flagged | No mould seen |
| Grey | `no_detection` or `camera_error` | Could not check (never healthy) |

Why these numbers: [evidence/threshold-check-2026-10-03.md](evidence/threshold-check-2026-10-03.md).

## Honest limits

- **Public data only.** Trained on a public Roboflow dataset of hand-held close-ups of oyster grow bags, not on our
  farm's camera. Farm accuracy will be lower.
- **Over-flags at amber.** On 752 held-out public photos, the 0.40 level missed no mould but also flagged 38% of
  healthy photos. The 0.80 level flagged 10% of healthy photos and missed 14 of 373 mould photos.
- **Two classes only:** contaminated or healthy. No mould type, and no "how early" claim yet.

## Contributing

Branches, the checks before a pull request, how to change the model, and what never to commit:
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licences and credits

- **This repo is private.** It is not open source.
- **Ultralytics YOLO** is AGPL-3.0. Keep this repo private, or get an Ultralytics licence, before publishing the
  code or selling a product that includes it.
- **Training data and the sample photos in `evidence/demo/`:** the oyster-mushroom fruiting-bag contamination
  dataset on Roboflow Universe, CC BY 4.0:
  https://universe.roboflow.com/oyster-mushroom-fruiting-bag/contamination-detection-ozkwx
