#!/usr/bin/env python
"""
Run the trained contamination detector LIVE on the laptop webcam.

  python webcam.py                 # default camera, opens a live window
  python webcam.py --cam 1         # if you have a second camera
  python webcam.py --conf 0.5      # only show more-confident detections
Press  q  in the window to quit.

NOTE: the model only knows two things -- "Healthy" bag vs "Contaminated" bag. So
point it at a mushroom bag, or at a PHOTO of one on your phone/another screen. If you
point it at your face or the room, it will still try to label whatever it sees as
healthy/contaminated -- that's expected nonsense, not a bug.
"""
import argparse
import os

# default weights = models/best.pt in this repo (override with --weights or SMARTPHSET_WEIGHTS)
DEFAULT_WEIGHTS = os.environ.get("SMARTPHSET_WEIGHTS") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "best.pt")

ap = argparse.ArgumentParser()
ap.add_argument("--weights", default=DEFAULT_WEIGHTS)
ap.add_argument("--cam", type=int, default=0, help="camera index (0 = default webcam)")
ap.add_argument("--conf", type=float, default=0.4, help="confidence threshold (higher = fewer, surer boxes)")
args = ap.parse_args()

from ultralytics import YOLO
print("Loading model... point the camera at a mushroom bag (or a photo of one). Press q to quit.")
YOLO(args.weights).predict(source=args.cam, show=True, conf=args.conf)
