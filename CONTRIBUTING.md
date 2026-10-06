# Contributing

How the team works on the SmartPhset AI. Start with the [README](README.md) and
[docs/run-the-bridge.md](docs/run-the-bridge.md).

## Who owns what

- **This repo (the AI and `bridge.py`):** Hout.
- **The website:** Hout, in [SmartPhset-Prototype-Frontend](https://github.com/menghoutishere-code/SmartPhset-Prototype-Frontend).
- **The Node backend and the hardware:** the engineer, who calls this repo's bridge.

The bridge's reply format ([docs/bridge-api.md](docs/bridge-api.md)) is shared with the website and the backend.
**Do not rename or remove a reply field** without agreeing it with both, and updating the website's
`src/app/api/images/route.ts` and `docs/api-contract.md` at the same time. Adding a new field is fine.

## Workflow

1. Make a branch: `git switch -c fix/short-name` (or `feat/...`, `model/...`, `docs/...`).
2. Commit, push the branch, open a pull request to `main` saying what changed and how you tested it.
3. Hout reviews and merges. Small doc fixes can go straight to `main`.

From Oct 20 to the National Challenge (Oct 23-25, 2026), only bug fixes, and nothing merged without testing on the
demo laptop.

## Before you open a pull request

Start the bridge and check the sample photos:

```powershell
$env:BRIDGE_API_KEY = "<any test key>"
python bridge.py --api-key $env:BRIDGE_API_KEY --port 8001
curl.exe -H "Authorization: Bearer <same key>" -H "Content-Type: image/jpeg" `
  --data-binary "@evidence/demo/image0.jpg" "http://localhost:8001/image?camera=test"
```

- A sample photo still gets a sensible result, and a request without the key gets `401`.
- If you changed the bridge's reply, the docs and the website are updated (see above).

## Changing the model

A new `models/best.pt` is a bigger change than code:

- Train and evaluate with the scripts in `training/` ([docs/training.md](docs/training.md)).
- In the pull request, put the new **test** scores next to the old ones, and the photo-level catches and false
  alarms at 0.40 and 0.80 on the **validation** set.
- **Do not tune on the test set**, and never quote validation numbers as the result.
- Update [docs/model-card.md](docs/model-card.md) and the `evidence/` folder in the same pull request.
- Keep the old model until the new one has been checked on real farm photos.

## Never commit

- **Keys:** `BRIDGE_API_KEY`, `ROBOFLOW_API_KEY`, `.env` files. Pass keys as environment variables only.
- **Datasets** (`data_det/` and similar), `runs/`, `bridge_log/` and the venv. `.gitignore` blocks these; do not
  force-add them.
- **Farm photos that show people,** or a farmer's name or location. Ask the farmer before using their bag photos for
  training.
- Files over about 50 MB. GitHub rejects files over 100 MB.

If a key is ever committed, tell Hout at once: the key has to be changed, because deleting the commit is not
enough.

## Honesty rules

The model is trained on public photos and **not validated on a farm**. In code messages, docs and pull requests:
nothing "guaranteed", no claim about how early it catches mould, no mould-type claims, and "could not check" never
means healthy.

## Licences

The repo is **private**. Ultralytics YOLO is AGPL-3.0, so do not make the repo public or copy this code into a
public project without talking to Hout first. Keep the Roboflow dataset credit (CC BY 4.0) wherever its photos are
used.
