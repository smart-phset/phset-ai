#!/usr/bin/env python
"""
Post-training HONEST evaluation + evidence pack for the SmartPhset oyster
contamination detector. Produces:
  - report.json            : test/val metrics + leakage check + failure counts
  - failure_false_alarms.png : grid of healthy bags wrongly flagged contaminated
  - failure_misses.png       : grid of contaminated bags the model missed
  - model-evidence.md        : a one-slide evidence summary with the REAL numbers

Honest checks built in:
  * TEST-set metrics (the 400 held-out images), reported next to val so we don't
    quote an inflated val number.
  * LEAKAGE check: Roboflow tripled each source image via 90-degree rotations
    (names like "IMG_0579_jpg.rf.<hash>.jpg"). We group by source stem and report
    how many source images appear in more than one split -- if >0, the val/test
    scores are optimistic.
  * FALSE-ALARM vs MISS montages -- the trust-relevant failures.

Usage:
  python evaluate_and_report.py --weights <best.pt> --data <data.yaml> \
         --dataroot <dataset root> --out <eval dir> --device cpu --imgsz 320
"""
import argparse
import glob
import json
import os
import re
from pathlib import Path

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CONTAM = 0  # class index 0 = Contaminated, 1 = Healthy (per data.yaml)


def source_stem(path: str) -> str:
    """'IMG_0579_jpg.rf.<hash>.jpg' -> 'IMG_0579' so rotated copies group together."""
    b = os.path.basename(path)
    b = re.split(r"\.rf\.", b)[0]
    b = re.sub(r"_jpg$", "", b, flags=re.I)
    b = re.sub(r"\.(jpg|jpeg|png|bmp|webp)$", "", b, flags=re.I)
    return b


def labels_for(img_path: str, dataroot: str, split: str):
    stem = Path(img_path).stem
    lp = Path(dataroot) / split / "labels" / f"{stem}.txt"
    cls = set()
    if lp.exists():
        for line in open(lp):
            line = line.strip()
            if line:
                cls.add(int(line.split()[0]))
    return cls


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--dataroot", required=True)
    ap.add_argument("--out", default="./eval_report")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--imgsz", type=int, default=320)
    ap.add_argument("--conf", type=float, default=0.25)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {}

    # 1. LEAKAGE check (source-image overlap across splits)
    splits = {}
    for s in ("train", "valid", "test"):
        files = [f for f in glob.glob(os.path.join(args.dataroot, s, "images", "*")) if Path(f).suffix.lower() in IMG_EXT]
        splits[s] = {"files": files, "sources": set(source_stem(f) for f in files)}
    leak_tv = splits["train"]["sources"] & splits["valid"]["sources"]
    leak_tt = splits["train"]["sources"] & splits["test"]["sources"]
    report["images_per_split"] = {s: len(v["files"]) for s, v in splits.items()}
    report["unique_sources_per_split"] = {s: len(v["sources"]) for s, v in splits.items()}
    report["leakage_train_val_sources"] = len(leak_tv)
    report["leakage_train_test_sources"] = len(leak_tt)

    from ultralytics import YOLO
    import numpy as np
    import cv2

    model = YOLO(args.weights)

    # 2. Held-out TEST metrics, plus VAL for comparison
    def metrics(split):
        r = model.val(data=args.data, split=split, imgsz=args.imgsz, device=args.device, verbose=False)
        return {"mAP50": round(float(r.box.map50), 4), "mAP50_95": round(float(r.box.map), 4),
                "precision": round(float(r.box.mp), 4), "recall": round(float(r.box.mr), 4)}
    report["test_metrics"] = metrics("test")
    report["val_metrics"] = metrics("val")

    # 3. FAILURE montages on the test set (image-level FP / FN for the Contaminated class)
    fp_imgs, fn_imgs = [], []  # (path, plotted_bgr)
    for img in splits["test"]["files"]:
        gt = labels_for(img, args.dataroot, "test")
        r = model.predict(img, imgsz=args.imgsz, device=args.device, conf=args.conf, verbose=False)[0]
        pred = set(int(c) for c in r.boxes.cls.tolist()) if r.boxes is not None and len(r.boxes) else set()
        gt_contam, pred_contam = (CONTAM in gt), (CONTAM in pred)
        if (not gt_contam) and pred_contam and len(fp_imgs) < 9:
            fp_imgs.append(r.plot())
        elif gt_contam and (not pred_contam) and len(fn_imgs) < 9:
            fn_imgs.append(r.plot())
        if len(fp_imgs) >= 9 and len(fn_imgs) >= 9:
            break
    report["failure_false_alarms_shown"] = len(fp_imgs)
    report["failure_misses_shown"] = len(fn_imgs)

    def montage(tiles, path, title):
        if not tiles:
            canvas = np.full((120, 640, 3), 40, np.uint8)
            cv2.putText(canvas, f"{title}: none found in test set", (12, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 2)
            cv2.imwrite(str(path), canvas); return
        cell = 320
        tiles = [cv2.resize(t, (cell, cell)) for t in tiles[:9]]
        while len(tiles) < 9:
            tiles.append(np.full((cell, cell, 3), 30, np.uint8))
        rows = [np.hstack(tiles[i:i + 3]) for i in (0, 3, 6)]
        grid = np.vstack(rows)
        bar = np.full((40, grid.shape[1], 3), 20, np.uint8)
        cv2.putText(bar, title, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imwrite(str(path), np.vstack([bar, grid]))

    montage(fp_imgs, out / "failure_false_alarms.png", "FALSE ALARMS (healthy flagged contaminated)")
    montage(fn_imgs, out / "failure_misses.png", "MISSES (contaminated called healthy)")

    json.dump(report, open(out / "report.json", "w"), indent=2)

    # 4. one-slide evidence markdown with the REAL numbers
    t, v = report["test_metrics"], report["val_metrics"]
    leak = report["leakage_train_val_sources"] + report["leakage_train_test_sources"]
    leak_line = ("clean -- no source image appears in more than one split"
                 if leak == 0 else
                 f"WARNING -- {report['leakage_train_val_sources']} sources shared train/val, "
                 f"{report['leakage_train_test_sources']} shared train/test; scores are optimistic")
    md = f"""# SmartPhset -- Model Evidence (first baseline)

> First-pass oyster contamination detector (YOLOv8n), trained locally on CPU. A
> proof the moat is buildable -- NOT a validated product. No guarantees; field
> accuracy is still [Phase-B].

## Headline (held-out TEST set, {report['images_per_split']['test']} images)
- **mAP@50: {t['mAP50']}**  |  mAP@50-95: {t['mAP50_95']}  |  precision: {t['precision']}  |  recall: {t['recall']}
- (val split, for comparison: mAP@50 {v['mAP50']}, precision {v['precision']}, recall {v['recall']})

## What it learned on
Public Roboflow set (CC BY 4.0): close-up photos / video frames of oyster-mushroom
**substrate-bag faces**, labelled Healthy vs Contaminated.
{report['images_per_split']['train']} train / {report['images_per_split']['valid']} val /
{report['images_per_split']['test']} test images (~{report['unique_sources_per_split']['train']}+
unique sources; the rest are 90-degree rotation augmentations).

## Honesty checks
- **Leakage check:** {leak_line}.
- **False alarms shown:** {report['failure_false_alarms_shown']} | **misses shown:** {report['failure_misses_shown']}
  (see `failure_false_alarms.png`, `failure_misses.png`).
- Single anonymous data source; hand-held close-ups, not a fixed grow-house camera;
  binary only (no mould type, no time/severity). Real grow-house accuracy will be lower.

## Evidence images
- Training curves: `results.png` | confusion matrix: `confusion_matrix.png`
- Demo detections: `oyster_demo/` | failures: `failure_false_alarms.png`, `failure_misses.png`

## The line to use in the pitch
"Our first baseline detector hit mAP@50 {t['mAP50']} on a public oyster
contamination set, trained in ~1.5 h on a laptop -- evidence the AI moat is buildable.
Field validation on our own time-stamped grow-house data is the next step."
"""
    (out / "model-evidence.md").write_text(md, encoding="utf-8")

    print("REPORT", json.dumps(report))
    print("EVAL_REPORT_DONE", str(out))


if __name__ == "__main__":
    main()
