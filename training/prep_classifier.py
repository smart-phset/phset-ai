#!/usr/bin/env python
"""
Prepare a clean-vs-contaminated image-classification split for the SmartPhset baseline.

Takes a raw folder of per-class subfolders (e.g. the Mendeley "Mushroom Disease Dataset":
  Healthy/  "Single Infected"/  "Mixed Infected/")
and writes an Ultralytics-style classification dataset:
  <out>/train/<class>/*.jpg
  <out>/val/<class>/*.jpg

Default is BINARY (Healthy vs Contaminated) to match SmartPhset's task framing
(clean vs contaminated). Use --multiclass to keep the original folders.

Usage:
  python prep_classifier.py --src ./data_raw --out ./data_cls --val 0.2
  python prep_classifier.py --src ./data_raw --out ./data_cls --multiclass
"""
import argparse
import shutil
from pathlib import Path

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def label_for(folder_name: str, binary: bool) -> str:
    n = folder_name.strip().lower()
    if binary:
        return "healthy" if "healthy" in n else "contaminated"
    return n.replace(" ", "_")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="raw dir with one subfolder per class")
    ap.add_argument("--out", required=True, help="output dataset dir (train/ + val/)")
    ap.add_argument("--val", type=float, default=0.2, help="validation fraction (0-1)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--multiclass", action="store_true", help="keep original class folders instead of binary")
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    if not src.is_dir():
        raise SystemExit(f"src not found: {src}")

    binary = not args.multiclass
    # gather images per destination label, deterministically
    buckets: dict[str, list[Path]] = {}
    for sub in sorted(p for p in src.iterdir() if p.is_dir()):
        label = label_for(sub.name, binary)
        imgs = sorted(p for p in sub.rglob("*") if p.suffix.lower() in IMG_EXT)
        buckets.setdefault(label, []).extend(imgs)

    if not buckets:
        raise SystemExit(f"no class subfolders with images found under {src}")

    if out.exists():
        shutil.rmtree(out)
    n_train = n_val = 0
    print(f"mode: {'binary' if binary else 'multiclass'}  val_frac={args.val}")
    for label, imgs in buckets.items():
        imgs = sorted(imgs)  # deterministic
        # stable interleaved split so val is spread across the folder, not the tail
        step = max(int(round(1 / args.val)), 2) if args.val > 0 else 10 ** 9
        train, val = [], []
        for i, p in enumerate(imgs):
            (val if (args.val > 0 and i % step == 0) else train).append(p)
        for split, items in (("train", train), ("val", val)):
            dst = out / split / label
            dst.mkdir(parents=True, exist_ok=True)
            for k, p in enumerate(items):
                shutil.copy2(p, dst / f"{label}_{split}_{k:05d}{p.suffix.lower()}")
        n_train += len(train)
        n_val += len(val)
        print(f"  {label:14s} total={len(imgs):5d}  train={len(train):5d}  val={len(val):5d}")

    # verification gate
    if n_train == 0 or n_val == 0:
        raise SystemExit("ERROR: empty train or val split -- check --src and --val")
    if len(buckets) < 2:
        raise SystemExit("ERROR: only one class found -- a classifier needs >=2 classes")
    print(f"DONE  classes={sorted(buckets)}  train={n_train}  val={n_val}  out={out}")


if __name__ == "__main__":
    main()
