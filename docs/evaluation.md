# Detector evaluation

Create `evaluation/healthy/`, `evaluation/contaminated/`, and
`evaluation/negative/` with independently labeled SmartPhset images. Nested
folders are supported. Images are processed sequentially in sorted relative-path
order; accepted extensions are JPG/JPEG, PNG, BMP, TIF/TIFF and WEBP,
case-insensitively. CSV output is already ignored by Git; do not force-add it.

```bash
.venv/bin/python tools/evaluate_detector.py --dataset evaluation \
  --model-provider local --output evaluation-results-local.csv

# Set ROBOFLOW_API_KEY in your environment first. This sends images to the
# configured hosted provider and can consume paid usage.
.venv/bin/python tools/evaluate_detector.py --dataset evaluation \
  --model-provider roboflow --output evaluation-results-roboflow.csv
```

Both commands accept `--conf` (default 0.4). Local options are `--weights`,
`--imgsz` (416), and `--device`. Hosted options are `--roboflow-model-id`
(`contamination-detection-ozkwx/1`) and `--roboflow-api-url`
(`https://serverless.roboflow.com`). `--data` aliases `--dataset`. No model is
loaded for an empty dataset. Nonempty hosted evaluation requires an environment
key and makes one sequential SDK call per readable image; the SDK can retry
internally. There is no fallback or application retry.

Scoring uses the existing SmartPhset verdict policy:

| Expected folder | Correct result | Incorrect outcomes |
| --- | --- | --- |
| healthy | GREEN / no_contamination_seen | contamination is a healthy false alert; no detection is healthy not detected |
| contaminated | RED or AMBER / contamination_suspected | no contamination is a miss; GREY contamination is separately reported as a low-confidence miss |
| negative | GREY / no_detection | GREEN is a false Healthy claim; any contamination verdict, including GREY, is a false contamination alert |

Errors, unreadable images and malformed results remain GREY/unavailable with
blank correctness and latency. They are excluded from inspected-image accuracy,
miss/false-alert counts and latency statistics; review unavailable counts
separately. `no_detection_count` counts successful no_detection results only.
Unknown labels follow the current verdict policy and cannot produce GREEN.
Confidence filtering can hide low-confidence boxes before scoring, so compare
providers with the same configuration and retain the CSV and invocation.

CSV records path, category, provider/model, verdict/severity, detection counts,
confidence, latency, correctness, outcome and a safe error code. Exception text
is omitted to avoid credential disclosure. Aggregate output includes availability,
correct/incorrect, accuracy, misses, low-confidence misses, false alerts, negative
false claims, no detections, average latency and p95 latency. P95 uses nearest
rank: sorted successful latencies at index `ceil(0.95 * n) - 1`; zero samples
produce null metrics. Latency is provider-reported inference time, including SDK
encoding/network for hosted calls, excluding image file loading. No warmup is
excluded.

These are image-level verdict metrics, not box-level mAP. Accuracy alone is
insufficient: review contamination misses, false alerts, unavailable images and
class balance. Use representative held-out images from the actual grow room.
Synthetic tests validate the tool only; published Roboflow metrics do not prove
SmartPhset quality. No real evaluation dataset was present when this tool was
implemented, and no model-quality conclusion has been made.
