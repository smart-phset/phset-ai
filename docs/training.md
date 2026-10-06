# Retrain and evaluate

You do not need this to run the AI; `models/best.pt` is ready. Use it to reproduce or improve the model.

```powershell
pip install -r requirements-extra.txt
cd training
```

The scripts write datasets and runs into the folder you run them from. Those folders are git-ignored.

## 1. Download the data and train

Needs a free Roboflow API key (roboflow.com -> Settings -> API key). The key is read from the environment and is
never written to disk. Do not commit it.

```powershell
$env:ROBOFLOW_API_KEY = "<your key>"
python train_detector.py --epochs 25 --imgsz 416 --batch 8 --device cpu --out ./data_det
```

- It downloads the dataset to `./data_det`, trains YOLOv8n, prints mAP, and saves demo predictions.
- The new model is at `runs/detect/<name>/weights/best.pt`.
- **CPU training is slow** (about 1.5 hours here). A free Google Colab GPU runs the same script much faster:
  use `--device 0`.
- **Gotcha:** Roboflow's `data.yaml` can contain `../train/images` paths that break. If training cannot find the
  images, edit `data.yaml` to use an absolute `path:` and `train: train/images`, `val: valid/images`,
  `test: test/images`.

## 2. Evaluate honestly

```powershell
python evaluate_and_report.py --weights runs/detect/<name>/weights/best.pt `
  --data ./data_det/data.yaml --dataroot ./data_det --out ./eval_report
```

It writes `report.json` (test and validation scores plus the leakage check), the failure picture grids and
`model-evidence.md`. Always quote the **test** numbers, not validation.

To choose alert levels, count photo-level catches and false alarms per threshold on the **validation** set (as in
`evidence/threshold-check-2026-10-03.md`). Do not tune on the test set.

## 3. Replace the model

1. Copy the new `best.pt` over `models/best.pt`.
2. Start the bridge and check the sample photos in `evidence/demo/`.
3. Update [model-card.md](model-card.md) and the evidence folder with the new numbers.
4. Update `model_version` in the website repo (`src/app/api/images/route.ts`).

## Classifier track (not used by the bridge)

For datasets with one folder per class (for example the Mendeley mushroom-bag set): `prep_classifier.py` builds a
train/validation split, `yolo classify train model=yolov8n-cls.pt data=<out> imgsz=224 epochs=30` trains, and
`eval_classifier.py` reports accuracy and the false-alarm rate. Kept for comparison; the product uses the detector.
