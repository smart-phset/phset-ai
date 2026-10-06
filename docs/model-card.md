# Model card: `models/best.pt`

| | |
|---|---|
| **Model** | YOLOv8n object detector (Ultralytics 8.4.71) |
| **Classes** | `Contaminated` (0), `Healthy` (1): boxes around grow-bag areas |
| **Trained** | 2026-06-20, on a laptop CPU, about 1.5 hours, 13 epochs, image size 416 |
| **Size** | 6.2 MB |
| **Input** | Any photo. The bridge resizes to 416 px internally (`--imgsz 416`) |
| **Status** | Demo baseline. **Not validated on a real farm.** |

## Training data

The public oyster-mushroom fruiting-bag contamination dataset on Roboflow Universe (CC BY 4.0):
https://universe.roboflow.com/oyster-mushroom-fruiting-bag/contamination-detection-ozkwx

- Hand-held close-up photos and video frames of oyster grow-bag faces, labelled healthy or contaminated.
- 9,504 training images (from 3,464 source photos, rotated copies added by Roboflow), 752 validation, 400 test.
- **Leakage check:** 0 source photos shared between training and validation; 1 of 400 test photos shares a source
  with training. See `evidence/report.json`.

## Results on held-out public photos

**Box-level (standard detector scores), test set of 400:**

| Metric | Test | Validation |
|---|---|---|
| mAP@50 | 0.920 | 0.952 |
| mAP@50-95 | 0.706 | 0.740 |
| Precision | 0.732 | 0.736 |
| Recall | 0.846 | 0.905 |

**Photo-level (what the farmer sees), validation set of 752 (373 contaminated, 379 healthy):**

| Alert level | Contaminated caught | Missed | Healthy wrongly flagged |
|---|---|---|---|
| Amber, 0.40 | 373/373 | 0 | 144/379 (38%) |
| Red, 0.80 | 359/373 | 14 | 37/379 (10%) |

Full table, including the test set: [../evidence/threshold-check-2026-10-03.md](../evidence/threshold-check-2026-10-03.md).

> **Correction:** the older `evidence/model-evidence.md` says "9 false alarms". That was a capped count of a picture
> montage. The real figure at 0.40 is 80 of 219 healthy test photos. Use the threshold check.

## Known limits

- **Domain shift.** All photos are public close-ups. A fixed camera in a real grow room, different light, or a
  different bag type will lower accuracy. It also over-flags on photos that are not grow bags.
- **Two classes only.** No mould type (green, black, cobweb), no severity, and no time labels, so "detects mould
  within hours" is not yet backed by data.
- **Over-flagging is deliberate at amber:** missing mould costs more than a farmer checking a healthy bag. The red
  level trades a few misses for far fewer false alarms.

## Next step

Collect time-stamped photos from our own pilot grow room, label them, and retrain or fine-tune
([training.md](training.md)). Then re-run the threshold check on farm photos.
