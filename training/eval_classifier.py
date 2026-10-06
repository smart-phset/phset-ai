#!/usr/bin/env python
"""
Evaluate a trained Ultralytics classification model for SmartPhset and report the
metrics that matter for farmer trust -- including the FALSE-ALARM RATE (healthy bags
wrongly flagged contaminated), which is the make-or-break metric.

Usage:
  python eval_classifier.py --weights runs/classify/train/weights/best.pt \
                            --data ./data_cls/val --out ./eval
"""
import argparse
from pathlib import Path

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", required=True, help="val dir with one subfolder per class")
    ap.add_argument("--out", default="./eval")
    args = ap.parse_args()

    from ultralytics import YOLO  # imported here so --help works without the dep
    import numpy as np
    from sklearn.metrics import confusion_matrix, classification_report

    val = Path(args.data)
    classes = sorted(p.name for p in val.iterdir() if p.is_dir())
    if len(classes) < 2:
        raise SystemExit(f"need >=2 class folders in {val}, found {classes}")
    idx = {c: i for i, c in enumerate(classes)}

    model = YOLO(args.weights)
    y_true, y_pred = [], []
    for c in classes:
        for p in sorted((val / c).rglob("*")):
            if p.suffix.lower() not in IMG_EXT:
                continue
            r = model(str(p), verbose=False)[0]
            pred_name = r.names[int(r.probs.top1)]
            y_true.append(idx[c])
            y_pred.append(idx.get(pred_name, -1))

    y_true, y_pred = np.array(y_true), np.array(y_pred)
    acc = float((y_true == y_pred).mean()) if len(y_true) else 0.0
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(classes))))

    print(f"\nclasses: {classes}")
    print(f"images evaluated: {len(y_true)}")
    print(f"accuracy: {acc:.4f}")
    # majority-class baseline (the bar a real model must clear)
    if len(y_true):
        _, counts = np.unique(y_true, return_counts=True)
        print(f"majority-class baseline: {counts.max() / counts.sum():.4f}")
    print("\nconfusion matrix (rows=true, cols=pred):")
    print("            " + "  ".join(f"{c[:8]:>8s}" for c in classes))
    for i, c in enumerate(classes):
        print(f"{c[:10]:>10s}  " + "  ".join(f"{v:8d}" for v in cm[i]))
    print("\n" + classification_report(y_true, y_pred, target_names=classes, zero_division=0))

    # FALSE-ALARM RATE: of truly-healthy bags, how many flagged contaminated
    if "healthy" in idx and len(classes) == 2:
        h = idx["healthy"]
        healthy_total = int((y_true == h).sum())
        false_alarms = int(((y_true == h) & (y_pred != h)).sum())
        misses = int(((y_true != h) & (y_pred == h)).sum())
        pos_total = int((y_true != h).sum())
        far = false_alarms / healthy_total if healthy_total else 0.0
        miss = misses / pos_total if pos_total else 0.0
        print(f"FALSE-ALARM RATE (healthy flagged contaminated): {far:.4f}  ({false_alarms}/{healthy_total})")
        print(f"MISS RATE (contaminated called healthy):         {miss:.4f}  ({misses}/{pos_total})")

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axp = plt.subplots(figsize=(4 + len(classes), 3 + len(classes)))
        axp.imshow(cm, cmap="Blues")
        axp.set_xticks(range(len(classes)), classes, rotation=45, ha="right")
        axp.set_yticks(range(len(classes)), classes)
        for i in range(len(classes)):
            for j in range(len(classes)):
                axp.text(j, i, cm[i, j], ha="center", va="center")
        axp.set_xlabel("predicted"); axp.set_ylabel("true"); axp.set_title(f"acc={acc:.3f}")
        fig.tight_layout(); fig.savefig(outdir / "confusion_matrix.png", dpi=120)
        print(f"saved {outdir / 'confusion_matrix.png'}")
    except Exception as e:  # plotting is optional
        print(f"(plot skipped: {e})")


if __name__ == "__main__":
    main()
