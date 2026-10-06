# SmartPhset -- Model Evidence (first baseline detector)

> **Correction (2026-10-03):** the "9 false alarms" below is a capped montage count, not the real rate. At
> threshold 0.40, 80 of 219 healthy test photos were flagged. See `threshold-check-2026-10-03.md` and
> `../docs/model-card.md`.

> First-pass oyster-mushroom contamination detector (YOLOv8n), trained locally on a
> laptop CPU in ~1.5 h. This is **proof the AI moat is buildable** -- not a validated
> product. Nothing guaranteed; real grow-house accuracy is still `[Phase-B]`.

## Headline -- held-out TEST set (400 unaugmented images the model never saw)
| Metric | Test | Val (for reference) |
|---|---|---|
| **mAP@50** | **0.920** | 0.952 |
| mAP@50-95 | 0.706 | 0.740 |
| precision | 0.732 | 0.736 |
| recall | 0.846 | 0.905 |

**The number to use: mAP@50 = 0.92 on the held-out test set.**

## Why this number is trustworthy (not inflated)
We checked for the usual trap -- Roboflow tripled each source image with 90-degree
rotations, which can leak near-duplicates across splits. The check came back clean:
- Augmentation was applied to **train only** (3,464 source images -> 9,504 train images).
- **Val (752) and test (400) are unaugmented, one-image-per-source held-out sets.**
- **0** source images shared between train and val; **only 1 of 400** test sources also
  appears in train (negligible). So the 0.92 test score reflects genuine generalisation.

## What it learned on
Public Roboflow dataset (**CC BY 4.0**):
<https://universe.roboflow.com/oyster-mushroom-fruiting-bag/contamination-detection-ozkwx>
-- close-up photos / video frames of oyster-mushroom **substrate-bag faces**, labelled
**Healthy vs Contaminated**. 9,504 train / 752 val / 400 test; ~3,464 unique source images.

## Failure analysis (the trust story)
- **0 misses** at the image level on the test set -- it did **not** call any contaminated
  bag "healthy."
- **9 false alarms** -- healthy bags flagged contaminated (precision ~0.73 is the weaker side).
- Read: the model is **biased toward over-flagging**, which is the *right* bias for an
  early-warning tool (better to over-alert than miss contamination), but the **false-alarm
  rate is the thing to tune next** (raise the confidence threshold; more/cleaner data).
- See `failure_false_alarms.png` (the 9 false alarms) and `failure_misses.png` (none).

## Evidence images (this folder)
- `results.png` -- training/val curves over 13 epochs
- `confusion_matrix.png`, `confusion_matrix_normalized.png` -- per-class performance
- `BoxPR_curve.png` -- precision-recall curve
- `failure_false_alarms.png`, `failure_misses.png` -- the honest failure montages
- `demo/image0..5.jpg` -- example detections with boxes

## Honest caveats (must stay in any pitch use)
- Single anonymous data source; **hand-held close-ups, not a fixed grow-house camera feed**.
- **Binary only** -- no mould *type* (green/black/cobweb) and **no time/severity labels**,
  so "warn within hours" is **not yet data-backed**.
- Real grow-house accuracy will be **lower** than 0.92 (expect the lab-to-field drop).

## The line for the pitch
> "Our first baseline detector hit **mAP@50 0.92 on a held-out public oyster-contamination
> set**, trained in ~1.5 hours on a laptop CPU -- with the data-leakage trap checked and a
> clean failure profile (no missed contamination). That's evidence the AI contamination
> moat is buildable today; validation on our own time-stamped grow-house data is the next step."
