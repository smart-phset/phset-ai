# SmartPhset AI — Codex Work Log

## Current status

Status: WAITING_FOR_COMMIT_APPROVAL

Current branch:
`feat/live-camera`

Last verified commit:
`696960153d8e276fbdfe90181fe4db1641abf341`

Last updated:
`2026-10-08T16:16:58+07:00`

## Goal

Integrate the existing oyster mushroom contamination model into SmartPhset AI
while preserving local-model support, ESP32-CAM streaming, backend publishing,
and SmartPhset verdict behavior.

## Completed phases

- [x] Phase 0 — repository inspection
- [x] Phase 1 — detector abstractions
- [ ] Phase 2 — local Ultralytics provider
- [ ] Phase 3 — Roboflow provider
- [ ] Phase 4 — live-camera integration
- [ ] Phase 5 — evaluation tooling
- [ ] Phase 6 — documentation and final validation

## Current phase

Phase 1 — detector abstractions COMPLETE; awaiting commit approval.

### Completed in this phase

- Read the previous work log completely and verified clean working tree, branch feat/live-camera, and HEAD 696960153d8e276fbdfe90181fe4db1641abf341 (`docs(ai): sync baseline work log`) before edits.
- Reconciled the previous log's pending checkpoint text against Git: log-only sync was approved and committed. Recorded its SHA as part of normal Phase 1 work.
- Added DetectionBox, DetectionResult, and the abstract Detector contract.
- Added summarize_detections for normalized boxes; retained summarize_result as a compatibility adapter for existing YOLO callers.
- Added focused type/interface, threshold, unrounded confidence, unknown/empty, mixed-class, prefix-policy, and compatibility tests.
- Completed only Phase 1; no local/Roboflow provider, SDK dependency, factory, camera integration, or evaluation tooling added.

### Files created

- detectors/__init__.py
- detectors/types.py
- detectors/base.py
- tests/test_detector_types.py

### Files modified

- live_camera.py — only type import, compatibility conversion, and provider-neutral verdict logic.
- CODEX_WORK_LOG.md — previous checkpoint reconciliation, Phase 1 results, and resume actions.

### Tests run

```text
.venv/bin/python -m unittest discover -s tests -p test_detector_types.py -v
PASS: 10 focused tests, 0.001s.
.venv/bin/python -m unittest discover -s tests -v
PASS: 33 tests, 0.063s (all 23 existing tests plus 10 new tests).
.venv/bin/python -m py_compile detectors/__init__.py detectors/types.py detectors/base.py live_camera.py tests/test_detector_types.py
PASS.
git diff --check
PASS.
```

### Important implementation decisions

- DetectionBox is frozen and lowercases labels at construction; confidence and original-frame coordinates remain unrounded.
- DetectionResult uses an independent default boxes list and retains timing, captured_at, provider, and model_id fields.
- Detector.detect accepts a BGR numpy frame; numpy is imported only for type checking so contract imports stay independent of model/numpy runtime dependencies. close defaults to a no-op.
- Verdict policy remains in live_camera.summarize_detections and consumes only normalized DetectionBox objects. Prefix matching, counts, maxima, messages, thresholds, and output JSON are preserved.
- summarize_result handles None/absent boxes and converts YOLO output into normalized boxes before delegating. Returned xyxy values remain JSON lists and confidence is never rounded.
- Camera loop, infer scheduling/options, ESP32 reconnect, preview, BackendPublisher, bridge.py, dependencies, and models/best.pt are unchanged.
- Keep pinned Ultralytics 8.4.71. Use uv, not pip installation, for future dependency operations.
- Baseline source work is complete in 8a1f7b3c1099a574d4cd8956f1febbf87adfb3fb; do not redo it.

### Known issues / blockers

- No Phase 1 blockers.
- Existing tests do not directly cover network reconnect/hardware; add camera integration coverage in Phase 4.
- Current model inference errors still terminate preview; remote failure recovery belongs to Phase 4.
- Hardware/GUI and real model quality have not been exercised in this phase. Tests use mocked camera/model/HTTP and no live Roboflow calls.

### Current Git state

```text
 M CODEX_WORK_LOG.md
 M live_camera.py
?? detectors/
?? tests/test_detector_types.py
```

Branch: feat/live-camera, ahead of origin/feat/live-camera by 2 commits; no push performed.
Last verified commit / previous checkpoint: 696960153d8e276fbdfe90181fe4db1641abf341.
No changes staged. Exactly six files are intended for the Phase 1 commit (the four created and two modified above).

### Next exact actions

1. Show Phase 1 checkpoint and stop before committing. Wait for explicit approval; do not start Phase 2.
2. On approval, re-read this log, run git status/branch/log, and reconcile any unexpected changes. Commit only the six intended Phase 1 files with the message below.
3. Report commit SHA and final Git status in chat; do not edit the log solely to store its own commit SHA, and do not push.
4. Only when Phase 2 is authorized: read the log and inspect Git; record the Phase 1 checkpoint SHA as part of Phase 2 work.
5. Phase 2: implement detectors/local_ultralytics.py with LocalUltralyticsDetector loading YOLO once, preserving weights/conf/device/imgsz behavior, converting predictions to normalized boxes and attaching inference timing/metadata. Add mocked provider tests.
6. Adapt existing local inference through that provider only within the approved Phase 2 scope, preserving webcam/network scheduling, reconnect, cleanup, verdicts, and publishing. Do not add Roboflow, SDK dependency, or provider-selection CLI yet.
7. Run local provider tests and existing regression suite, update this log, and stop before the Phase 2 checkpoint commit.

## Commit checkpoint

Phase 0 baseline and log-only sync: COMPLETE.
Phase 1 implementation: COMPLETE, not committed.

Commit required: YES — exactly the six Phase 1 files listed above.

Suggested commit message:

```text
refactor(ai): introduce provider-neutral detection interface
```

Commit approved by user: NO.

Commit SHA:
`PENDING — report in chat after approval; record at the beginning of the next phase.`

## Checkpoint workflow — user revision

This workflow supersedes the plan's instruction to update the log with a checkpoint's own SHA immediately after committing.

- Before each checkpoint commit, record the completed phase, tests/results, files changed, Git state, and exact next actions in this log; include it in that commit.
- After committing, report the SHA and final Git status in chat. Do not edit this log solely to insert that commit's own SHA.
- At the beginning of the NEXT authorized phase, inspect git log and record the previous checkpoint SHA as part of that phase's normal work.
- Each checkpoint should end with a clean working tree. Commit approval remains mandatory. Do not push without explicit authorization.

## Resume instructions

When continuing:

1. Read this file first.
2. Run `git status`.
3. Confirm the current branch and last commit.
4. Continue from **Next exact actions**.
5. Do not redo completed phases.
