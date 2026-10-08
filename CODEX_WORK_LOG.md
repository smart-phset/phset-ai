# SmartPhset AI — Codex Work Log

## Current status

Status: WAITING_FOR_COMMIT_APPROVAL

Current branch:
`feat/live-camera`

Last verified commit:
`f5cbf5e2c07e454b7d00992b7f8666bbf14cee61`

Last updated:
`2026-10-08T16:24:08+07:00`

## Goal

Integrate the existing oyster mushroom contamination model into SmartPhset AI
while preserving local-model support, ESP32-CAM streaming, backend publishing,
and SmartPhset verdict behavior.

## Completed phases

- [x] Phase 0 — repository inspection
- [x] Phase 1 — detector abstractions
- [x] Phase 2 — local Ultralytics provider
- [ ] Phase 3 — Roboflow provider
- [ ] Phase 4 — live-camera integration
- [ ] Phase 5 — evaluation tooling
- [ ] Phase 6 — documentation and final validation

## Current phase

Phase 2 — local Ultralytics provider COMPLETE; awaiting user-created commit.

### Completed in this phase

- Read the previous log fully before editing. Verified project SmartPhset-AI, origin https://github.com/smart-phset/phset-ai.git, branch feat/live-camera, clean tree, and local HEAD equal to the recorded origin/feat/live-camera ref.
- Reconciled Phase 1 as committed and pushed by the user: f5cbf5e2c07e454b7d00992b7f8666bbf14cee61 (`refactor(ai): introduce provider-neutral detection interface`). Recorded this previous checkpoint SHA in normal Phase 2 work. No fetch was performed; origin state refers to the locally recorded remote-tracking ref.
- Added LocalUltralyticsDetector implementing Detector, loading YOLO once and returning normalized DetectionResult.
- Routed the live camera's existing single inference worker through the local provider and provider-neutral summary conversion.
- Added mocked tests for single loading, prediction options, custom imgsz/conf/device, normalized labels, unrounded confidence, original-frame coordinates, metadata, empty/absent boxes, backend-compatible summary, and propagated inference failure.
- No Phase 3 work, provider-selection CLI, SDK dependency, model weight changes, or dependency upgrades.

### Files created

- detectors/local_ultralytics.py
- tests/test_local_ultralytics_detector.py

### Files modified

- live_camera.py
- CODEX_WORK_LOG.md

### Tests run

```text
.venv/bin/python -m unittest discover -s tests -p test_local_ultralytics_detector.py -v
PASS: 6 focused tests, 0.009s.
.venv/bin/python -m unittest discover -s tests -v
PASS: 39 tests, 0.082s, including all 33 previous tests.
.venv/bin/python -m py_compile detectors/local_ultralytics.py live_camera.py tests/test_local_ultralytics_detector.py
PASS.
git diff --check
PASS.
```

### Important implementation decisions

- Lazy Ultralytics import and optional model_factory test hook avoid real model loading in tests. Existing installed/pinned Ultralytics 8.4.71 is unchanged.
- Provider constructor accepts weights, confidence, optional device, and imgsz (default 416). Only configured device is sent to predict; verbose=False remains unchanged.
- detect returns lowercase labels, full floating-point confidence/xyxy, UTC Z captured_at at inference start, measured inference_ms, provider=local, and model_id equal to the weights path.
- run_camera constructs one detector; the existing single executor submits infer_detector with a copied frame, preserving scheduling and queue behavior.
- infer(model, frame, args) remains a compatibility entry point wrapping the already-loaded model through the same provider; it does not reload weights. The live loop uses infer_detector directly.
- Summary retains the existing backend fields and JSON box lists; no provider metadata is injected into the backend schema.
- Existing webcam/network opening, reconnect, publishing, thresholds, and q/Ctrl+C cleanup are unchanged. Local provider inherits the no-op close because no additional resources are owned.
- Use uv-compatible dependency commands. No dependency operation was needed in Phase 2.

### Known issues / blockers

- No Phase 2 blockers.
- Hardware/GUI/real model inference have not been exercised; these tests are mocked and make no live Roboflow calls.
- Network reconnect still lacks direct automated coverage; preserve baseline code and add coverage during Phase 4.
- Current model failure propagation is unchanged; hosted-service recovery belongs to Phase 4.

### Current Git state

```text
 M CODEX_WORK_LOG.md
 M live_camera.py
?? detectors/local_ultralytics.py
?? tests/test_local_ultralytics_detector.py
```

Project: SmartPhset-AI. Repository: phset-ai. Branch: feat/live-camera.
Last verified commit / previous checkpoint: f5cbf5e2c07e454b7d00992b7f8666bbf14cee61.
Local HEAD matches the recorded origin/feat/live-camera ref. No changes staged. No commit or push performed by the agent.

### Next exact actions

1. Show the four-file Phase 2 checkpoint and exact staging/commit commands to the user; stop. The user creates commits.
2. Wait for the user to commit and explicitly authorize Phase 3. Do not start it now.
3. On continuation, read this log, run git status/branch/log, verify the user-created Phase 2 commit and intended files, reconcile origin state, and record its SHA as normal Phase 3 work.
4. Phase 3: inspect SDK availability/API and dependency compatibility using uv; add inference-sdk==1.7.3 unless a deliberately compatible version is already pinned. Preserve Ultralytics and unrelated dependency versions.
5. Implement RoboflowDetector for contamination-detection-ozkwx/1, supported in-memory input, header API-key transport, bounded timeout, center-box conversion, metadata, and safe error handling. Read ROBOFLOW_API_KEY from the environment; never log secrets.
6. Add mocked Roboflow normalization/configuration/failure tests, run relevant/full tests and syntax/diff checks, update this log, and stop with user commit details. Do not add provider-selection/live remote integration before Phase 4.

## Commit checkpoint

Phase 0 and Phase 1: COMPLETE and committed.
Phase 2: COMPLETE, not committed.

Files to stage: detectors/local_ultralytics.py, tests/test_local_ultralytics_detector.py, live_camera.py, CODEX_WORK_LOG.md.

Suggested commit message:

```text
refactor(ai): wrap local YOLO inference as detector provider
```

Commit owner: USER. The agent must NEVER run git add, git commit, or git push.
Commit SHA: PENDING user-created commit; record when the next phase begins.

## Checkpoint workflow — user revision

- User creates all commits. Agent provides project/repository/branch, exact files, commit message, commands, tests, Git status, and next phase at each checkpoint, then stops.
- Before a checkpoint, record completed work, tests/results, changed files, Git state, and next actions in this log for inclusion in the user-created commit.
- Do not edit this log solely to insert that commit's own SHA afterward. Record the previous checkpoint SHA at the beginning of the next authorized phase.
- Do not push or begin the next phase without user instruction.

## Resume instructions

When continuing:

1. Read this file first.
2. Run `git status`.
3. Confirm the current branch and last commit.
4. Continue from **Next exact actions**.
5. Do not redo completed phases.
