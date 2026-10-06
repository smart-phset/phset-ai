#!/usr/bin/env python
"""
Track B: train a YOLO-nano OYSTER contamination DETECTOR on the Roboflow D1 dataset.

Needs a free Roboflow API key (roboflow.com -> Settings -> API key). The exact
workspace / project / version come from the dataset's "Download Dataset -> show
download code" snippet; the defaults below target the oyster fruiting-bag set, but
pass --workspace/--project/--version if the snippet differs.

Usage (key via env, never written to disk):
  export ROBOFLOW_API_KEY=...        # or set on Windows
  python train_detector.py --epochs 25 --imgsz 416 --batch 8 --device cpu --out <data_dir>

Verification gates: data.yaml present -> best.pt produced -> mAP reported -> demo predictions saved.
"""
import argparse
import glob
import os
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=os.environ.get("ROBOFLOW_API_KEY", ""))
    ap.add_argument("--workspace", default="oyster-mushroom-fruiting-bag")
    ap.add_argument("--project", default="contamination-detection-ozkwx")
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--imgsz", type=int, default=416)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", default="./data_det")
    args = ap.parse_args()
    if not args.key:
        raise SystemExit("No API key. Set ROBOFLOW_API_KEY or pass --key (not stored).")

    # 1. download
    from roboflow import Roboflow
    rf = Roboflow(api_key=args.key)
    proj = rf.workspace(args.workspace).project(args.project)
    ds = proj.version(args.version).download("yolov8", location=str(Path(args.out)))
    data_yaml = Path(ds.location) / "data.yaml"
    print("DATA_YAML", data_yaml, "exists:", data_yaml.exists())
    if not data_yaml.exists():
        raise SystemExit("data.yaml not found after download -- check workspace/project/version")

    # 2. train
    from ultralytics import YOLO
    m = YOLO(args.model)
    res = m.train(data=str(data_yaml), imgsz=args.imgsz, epochs=args.epochs,
                  batch=args.batch, device=args.device, plots=True)
    best = Path(res.save_dir) / "weights" / "best.pt"
    print("BEST_EXISTS", best.exists(), best)
    if not best.exists():
        raise SystemExit("training did not produce best.pt")

    # 3. eval (mAP, precision/recall)
    mm = YOLO(str(best))
    val = mm.val(data=str(data_yaml), device=args.device)
    print("mAP50:", getattr(val.box, "map50", None), " mAP50-95:", getattr(val.box, "map", None),
          " precision:", getattr(val.box, "mp", None), " recall:", getattr(val.box, "mr", None))

    # 4. demo predictions
    cand = (glob.glob(str(Path(ds.location) / "valid" / "images" / "*"))
            or glob.glob(str(Path(ds.location) / "test" / "images" / "*"))
            or glob.glob(str(Path(ds.location) / "train" / "images" / "*")))[:6]
    if cand:
        mm.predict(cand, save=True, device=args.device)
        print("SAVED_DEMO_PREDICTIONS", len(cand))
    print("DETECTOR_DONE")


if __name__ == "__main__":
    main()
