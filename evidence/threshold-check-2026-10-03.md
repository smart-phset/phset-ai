# Threshold check: photo-by-photo results (2026-10-03)

Model: `best.pt` (YOLOv8n, trained 2026-06-20), `imgsz=416`.

**Method:**
- A photo counts as **flagged** if any "Contaminated" box reaches the threshold.
- **Ground truth:** a photo is contaminated if its label file has any class-0 box.
- **Data:** public Roboflow dataset, held-out splits only. **Not farm photos.**

## Validation set (752 photos: 373 contaminated, 379 healthy)

Use this set to choose thresholds.

| Threshold | Contaminated caught | Missed | Healthy wrongly flagged |
|---|---|---|---|
| 0.40 | 373/373 | 0 | 144/379 (38%) |
| 0.60 | 371/373 | 2 | 102/379 (27%) |
| 0.65 | 369/373 | 4 | 94/379 (25%) |
| 0.70 | 369/373 | 4 | 82/379 (22%) |
| 0.75 | 368/373 | 5 | 70/379 (18%) |
| 0.80 | 359/373 | 14 | 37/379 (10%) |

## Test set (400 photos: 181 contaminated, 219 healthy)

Reference only. Do not tune on this set.

| Threshold | Contaminated caught | Missed | Healthy wrongly flagged |
|---|---|---|---|
| 0.40 | 181/181 | 0 | 80/219 (37%) |
| 0.70 | 181/181 | 0 | 55/219 (25%) |
| 0.80 | 173/181 | 8 | 17/219 (8%) |

## Notes

- **Correction:** the earlier "9 false alarms" in `model-evidence.md` came from a capped montage count. At
  threshold 0.4 the true figure is 80 of 219 healthy test photos.
- **Plan:** amber at 0.40, red at 0.80 (see `product-research/prototype-build-plan-2026-10.md`).
- Alerts must use the highest **contaminated** box confidence (`max_contaminated_conf` in `bridge.py`), not the
  highest of all boxes.
