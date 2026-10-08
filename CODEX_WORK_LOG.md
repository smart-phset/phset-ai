# SmartPhset AI — Codex Work Log

## Current status

Status: IN_PROGRESS

Current branch:
`feat/live-camera`

Last verified commit:
`bb81eca2f148681ea782b11d9925ffeac357be8a`

Last updated:
2026-10-08T16:59:02.076347+07:00

## Goal

Integrate the existing oyster mushroom contamination model into SmartPhset AI
while preserving local-model support, ESP32-CAM streaming, backend publishing,
and SmartPhset verdict behavior.

## Completed phases

- [x] Phase 0 — repository inspection
- [x] Phase 1 — detector abstractions
- [x] Phase 2 — local Ultralytics provider
- [x] Phase 3 — Roboflow provider
- [x] Phase 4 — live-camera integration
- [x] Phase 5 — evaluation tooling
- [ ] Phase 6 — documentation and final validation

## Current phase

Phase 5 — detector evaluation tooling COMPLETE. Implementation/validation passed; checkpoint commit/push next. Phase 6 not started.

### Completed in this phase

- Read previous log fully before editing and reconciled user-created Phase 2 commit f2aaf30e8a3b1f832f32a156dc798c7f879c173d (`refactor(ai): wrap local YOLO inference as detector provider`). Its files are exactly CODEX_WORK_LOG.md, detectors/local_ultralytics.py, live_camera.py, tests/test_local_ultralytics_detector.py.
- Startup tree was clean in SmartPhset-AI, repository https://github.com/smart-phset/phset-ai.git, branch feat/live-camera. Branch is one commit ahead of recorded origin/feat/live-camera; user reported committing, not pushing, Phase 2. No fetch or push performed.
- Recorded the previous checkpoint SHA as normal Phase 3 work.
- Added the permanent EXTERNAL TECHNOLOGY RESEARCH RULE below.
- Researched official registry, docs, model page, release notes, and exact v1.7.3 source before writing provider code.
- Implemented standalone RoboflowDetector and DetectorUnavailableError, in-memory SDK calls, normalized detections/metadata, strict malformed-response rejection, safe exception messages, and cancellable async request deadline behind synchronous detect().
- Added 11 mocked unit tests plus 2 installed-SDK tests with mocked outbound transport covering configuration, environment keys, NumPy identity, conversion, precision, classes, multiple/empty/malformed results, failures, deadline cancellation, metadata, and no output. Tests prohibit accidental socket/requests calls.
- Existing live camera/local provider/backend/models and installed dependency environment remain untouched. Candidate requirements edits are recorded below. No Phase 4 integration or CLI.

### Files created

- detectors/roboflow_detector.py
- tests/test_roboflow_detector.py

### Files modified

- CODEX_WORK_LOG.md — research, implementation progress, new automatic commit/push workflow and final installed-SDK verification and completion results.
- requirements.txt — numpy==2.4.4 changed to the metadata-compatible candidate numpy==2.3.5 and inference-sdk==1.7.3 added after user approval and recorded research. All other existing pins unchanged. User installed the combined requirements successfully; agent independently verified installed metadata, imports, dry-run satisfaction, and compatibility.

### Research date and official sources checked

Research date: 2026-10-08 (Asia/Phnom_Penh).

- https://pypi.org/project/inference-sdk/ and https://pypi.org/project/inference-sdk/1.7.3/ — direct pages show latest release 1.7.3, released 2026-10-02, Python >=3.10,<3.14; Python 3.11 is supported. Initial search snippets showed stale 1.6.0 information; direct current pages corrected that. No newer stable release is shown there.
- https://github.com/roboflow/inference/releases/tag/v1.7.3 and https://github.com/roboflow/inference/releases — reviewed release context and v1.5.0 header-auth addition; no deprecation of infer/infer_async found in checked sources. This is not a claim that every SDK feature was audited.
- https://universe.roboflow.com/oyster-mushroom-fruiting-bag/contamination-detection-ozkwx — confirms model contamination-detection-ozkwx/1, Healthy/Contaminated classes, object-detection task, CC BY 4.0 attribution to Oyster Mushroom Fruiting Bag, serverless endpoint, and header-auth code snippet. No test image uploaded or inference performed.
- https://inference.roboflow.com/inference_helpers/inference_sdk/ — docs explicitly show cv2.imread NumPy input to infer and supported infer_async; output is plain Python dictionaries. No temporary files or manual encoding needed in this provider.
- https://github.com/roboflow/inference/blob/v1.7.3/inference_sdk/http/client.py — fetched exact tagged source through the GitHub connector. Constructor accepts api_url/api_key; infer and infer_async accept inference_input/model_id. No timeout argument. Async requests use aiohttp and context-managed sessions.
- https://github.com/roboflow/inference/blob/v1.7.3/inference_sdk/http/entities.py — tagged source: InferenceConfiguration supports api_key_transport=header, confidence_threshold, client_downsizing_disabled; it has NO request timeout field. Header means Authorization: Bearer only, no URL/body API key.
- https://github.com/roboflow/inference/blob/v1.7.3/inference_sdk/http/utils/loaders.py — tagged source confirms np.ndarray input is encoded internally by SDK; no provider disk I/O/manual JPEG encoding.
- https://github.com/roboflow/inference/blob/v1.7.3/inference_sdk/http/utils/executors.py — tagged source confirms sync session.get/post omits timeout. Async uses aiohttp.ClientSession context, cancellable request coroutines, and SDK-internal retries (up to 3 on transient statuses/connections). One SDK inference invocation per detect does NOT guarantee one HTTP attempt because of these SDK retries.
- https://github.com/roboflow/inference/blob/v1.7.3/inference_sdk/http/errors.py — HTTPClientError base and HTTPCallErrorError subtype verified; transport exceptions can also originate from aiohttp/requests.
- https://github.com/roboflow/inference/blob/v1.7.3/requirements/requirements.sdk.http.txt — tagged source requires requests>=2.33.0,<3; numpy>=2.0.0,<2.4.0; pillow>=12.3,<13; aiohttp~=3.14.0; supervision>=0.26; dataclasses-json~=0.6.0; tldextract~=5.1.2; backoff~=2.2.0; py-cpuinfo~=9; opencv-python>=4.8.1.78,<=4.13.0; urllib3>=1.26,<3.
- https://roboflow.com/pricing and https://docs.roboflow.com/deploy/serverless-hosted-api-v2 — official usage context reviewed. Current PyPI project description says serverless bills per image with model-dependent rates (not a generic per-call fixed price). Exact account/model rate, quota, and authorization were not verified. No live/paid calls made.

### Differences from plan and implementation decisions

- SDK release 1.7.3 and Python compatibility match the plan, but actual dependency compatibility does NOT: project pins/installs numpy 2.4.4 while SDK tagged requirements demand <2.4. Installed requests is 2.28.1, below SDK >=2.33.0. Installed pillow 12.3.0 satisfies the SDK. Keep Ultralytics 8.4.71 unchanged.
- Do not install with --no-deps or retain the conflicting NumPy 2.4.4 pin. User APPROVED adjusting only SDK-required versions after compatibility checks. Candidate numpy==2.3.5 is supported on Python >=3.11 per https://pypi.org/project/numpy/2.3.5/ and satisfies every active NumPy requirement in the existing installed distribution metadata (scipy, ultralytics, torchvision, contourpy, matplotlib, opencv-python, ultralytics-thop), as checked with packaging.requirements. Candidate requests>=2.33.0 is required by the SDK and its release page https://pypi.org/project/requests/2.33.0/ was checked. Decision BEFORE changing pins: use numpy==2.3.5 and inference-sdk==1.7.3, preserving all other existing requirements pins. This is metadata compatibility only; combined resolver/install/runtime checks remain incomplete because DNS is blocked. Approved proposed SDK remains inference-sdk==1.7.3; no automatic newer release upgrade.
- No invented timeout configuration: use official infer_async(frame, model_id=...) inside asyncio.wait_for(timeout=8) and asyncio.run in synchronous detect, called outside an existing event loop by the sole inference worker. Direct NumPy object is passed unchanged. This differs from the plan's synchronous infer sketch and is necessary because its API has no timeout setting. SDK aiohttp contexts close on cancellation; a mocked hung coroutine cancellation test passes. Actual installed SDK cancellation still needs verification after installation.
- SDK handles encoding, auth, confidence configuration, HTTP, and its retries. Application adds no extra inference calls/retries. Network deadline bounds coroutine waits/retries; local synchronous image encoding itself is not preemptible by asyncio.
- All malformed predictions reject the entire inspection, including a malformed contamination box alongside Healthy, so invalid data cannot be silently dropped to create GREEN. Unknown classes remain unknown and GREY under existing verdict policy.
- No SDK exception text, request URL/body, or chained traceback is surfaced by provider errors. No API key hardcoded/logged.

### Tests and environment checks

```text
.venv/bin/python -m unittest discover -s tests -p test_roboflow_detector.py -v
PASS: 11 mocked tests, 0.059s.
.venv/bin/python -m unittest discover -s tests -v
PASS: 50 tests, 0.138s, including all 39 prior tests.
.venv/bin/python -m py_compile detectors/roboflow_detector.py tests/test_roboflow_detector.py
PASS.
git diff --check
PASS.
UV_CACHE_DIR=/tmp/smartphset-uv-cache uv pip check --python .venv/bin/python
PASS: existing 36 installed packages compatible; inference-sdk NOT installed, so this does not establish combined SDK compatibility.
UV_CACHE_DIR=/tmp/smartphset-uv-cache uv pip install --python .venv/bin/python --dry-run inference-sdk==1.7.3
FAILED: PyPI DNS lookup unavailable in shell; no packages modified.
Combined candidate dry runs (explicit numpy/SDK/Ultralytics/OpenCV, then -r requirements.txt) also failed DNS before dependency resolution. No successful combined resolver result is claimed.
```

Initial tests exposed a test-clock patch interfering with asyncio's shared time.monotonic; corrected by importing/patching the provider-local monotonic reference. Final focused/full reruns pass without coroutine warnings.

### Final installed API and compatibility validation

Status: COMPLETE. Research/validation date: 2026-10-08.

- Resumed the same four unfinished files, not a reimplementation. HEAD remained f2aaf30e8a3b1f832f32a156dc798c7f879c173d; branch feat/live-camera one commit ahead of recorded origin before this checkpoint.
- User restored package access and installed using `UV_CACHE_DIR=/tmp/smartphset-uv-cache uv pip install --python .venv/bin/python --index-strategy unsafe-best-match -r requirements.txt`. Agent independently verified actual installed versions and all required imports.
- NumPy 2.4.4 -> 2.3.5 is necessary for SDK metadata numpy>=2,<2.4. requests 2.28.1 -> 2.34.2 satisfies SDK requests>=2.33,<3. These changes are SDK-required and user-authorized, not unrelated upgrades.
- Installed versions: inference-sdk 1.7.3, numpy 2.3.5, requests 2.34.2; protected ultralytics 8.4.71, torch 2.12.1+cpu, torchvision 0.27.1+cpu, opencv-python 4.10.0.84 unchanged. import inference_sdk/numpy/requests/ultralytics/torch/torchvision/cv2 all PASS.
- https://docs.astral.sh/uv/concepts/indexes/#searching-across-multiple-indexes checked: uv default first-index limits each package to the first index containing it. With existing PyTorch extra index, candidate versions on PyPI can be excluded by that policy. User's unsafe-best-match command considers the combined index candidates and successfully installed requirements. The earlier DNS failure was a separate issue. Exact prior first-index resolver error was not captured here; do not claim its contents were independently reproduced. No index/project config rewrite made.
- `UV_CACHE_DIR=/tmp/smartphset-uv-cache uv pip install --python .venv/bin/python --index-strategy unsafe-best-match --offline --dry-run -r requirements.txt` PASS: checked 6 direct requirements; would make no changes. Combined installed resolution is satisfied, with no extra installation by agent.
- Inspected actual installed InferenceHTTPClient signature (api_url, api_key=None), InferenceConfiguration dataclass signature, infer_async source, NumPy loader source, and SDK exception classes. infer_async's decorator hides its Python signature as (*args, **kwargs); inspected underlying source confirms inference_input/model_id.
- Verified real configuration normalizes header transport and maps confidence_threshold to confidence in request parameters. SDK numpy loader handles BGR ndarray encoding internally. No provider API changes were required.
- Added installed-SDK tests exercising real client configuration, ndarray encoding, model endpoint, header credentials absent from query/body, exact confidence parameter, normalized output, SDK exception wrapping, and cancellation closing the mocked aiohttp session. All outbound transport is mocked/blocked; no real key or live/paid inference required.

### Final tests run and results

```text
.venv/bin/python -m unittest discover -s tests -p test_roboflow_detector.py -v
PASS: 13 tests, 1.300s (11 unit + 2 installed SDK with mocked transport).
.venv/bin/python -m unittest discover -s tests -v
PASS: 52 tests, 1.145s.
.venv/bin/python -m compileall -q detectors tests live_camera.py backend_publisher.py bridge.py
PASS.
git diff --check
PASS.
UV_CACHE_DIR=/tmp/smartphset-uv-cache uv pip check --python .venv/bin/python
PASS: 58 packages; all installed packages compatible.
Basic imports for inference_sdk, numpy, requests, ultralytics, torch, torchvision, cv2
PASS.
```

### Known limitations and intentional non-changes

- Earlier DNS/dependency blockers are resolved by user installation and independent validation above. Historical failed attempts/research are retained above as history, not current blockers.
- No real hosted inference, camera GUI/hardware test, backend connection, or local model quality evaluation performed. Automated tests are mocked.
- Async deadline bounds network awaits/retries; synchronous image encoding cannot be preempted. SDK internal retries remain; one detect means one SDK invocation, not necessarily one HTTP attempt.
- Camera loop, CLI, local provider, reconnect, BackendPublisher, severity thresholds, model weights and protected package versions intentionally unchanged in Phase 3. Phase 4 owns live provider integration.
- No runtime model acceptance/accuracy claim. CC BY 4.0 attribution source recorded; final documentation/evaluation remains later phases.

### Current Git state before checkpoint commit

```text
 M CODEX_WORK_LOG.md
 M requirements.txt
?? detectors/roboflow_detector.py
?? tests/test_roboflow_detector.py
```

Project SmartPhset-AI; repository phset-ai; branch feat/live-camera. Intended commit is exactly these four files.
Last verified previous checkpoint: f2aaf30e8a3b1f832f32a156dc798c7f879c173d.

### Next exact actions

1. Review full diff/status; stage only detectors/roboflow_detector.py, tests/test_roboflow_detector.py, requirements.txt, CODEX_WORK_LOG.md.
2. Commit with `feat(ai): add Roboflow mushroom detection provider`, push feat/live-camera to origin, verify push and clean working tree. Report commit SHA in chat; no post-commit log-only edit.
3. If push fails, preserve the validated local commit; update log with exact blocker and do not start Phase 4 until push/clean gate succeeds.
4. At Phase 4 start, read this log, inspect Git and record the Phase 3 SHA as normal Phase 4 work. Research relevant official SDK/camera/concurrency APIs before changes.
5. Phase 4: build_detector factory, --model-provider (local default), --roboflow-model-id, --roboflow-api-url, --imgsz; fail fast on missing API key with no secret output or fallback. Roboflow must not require local weights.
6. Integrate providers into the existing single-worker scheduler, preserve webcam/network capture/reconnect, preview, backend payload identity, verdict thresholds and q/Ctrl+C cleanup. Keep hosted failures separate from camera failures; preview continues, unavailable/GREY replaces stale/error state, retries occur at scheduled rate, no fake GREEN, no local fallback. Start hosted monitoring at 1 FPS.
7. Add mocked factory/CLI/remote failure/retry/single-worker/publisher-equivalence/camera reconnect/cleanup tests. Run focused/full regressions, syntax/diff/compatibility gates; log COMPLETE before commit/push (`feat(camera): support selectable AI detection providers`).
8. Do not start evaluation tooling or final documentation phases as part of Phase 4.

## Commit checkpoint

Phase 3 — Roboflow provider
Status: COMPLETE.
Exact commit message: `feat(ai): add Roboflow mushroom detection provider`.
Files: detectors/roboflow_detector.py, tests/test_roboflow_detector.py, requirements.txt, CODEX_WORK_LOG.md.
Agent authorized to commit/push without approval after reviewing intended diff. No post-commit SHA-only log edit; record SHA when Phase 4 begins.

## Checkpoint workflow — latest user revision (effective immediately)

This supersedes ALL earlier manual-commit/approval instructions in this log and the original plan.

- Agent owns implementation, staging, committing, and pushing completed work. No commit approval or manual user commit is required.
- BEFORE every commit, update this log with phase/job name, status COMPLETE, research, implementation decisions, created/modified files, dependency/version changes, tests/results, compatibility checks, known issues, intentional non-changes, exact commit message, and next phase/exact actions.
- Completion gates: focused tests, full regressions, syntax/compile checks, git diff --check, and applicable dependency compatibility checks must all pass. Review Git status/diff; stage ONLY intended files; commit with the recorded conventional message; push the current branch to existing upstream/origin; verify push and clean final Git status.
- Report project, repository, branch, commit SHA/message, committed files, tests, push result, final Git status, and next phase.
- Never dirty the tree after committing solely to record that commit's own SHA. Report it in chat; record it at the beginning of the next phase as normal work.
- If any required test, dependency resolution, installation verification, or compatibility check fails: do NOT commit/push or mark complete. Update this log with exact blocker/state, preserve unfinished work, and stop only when human input or an external-state change is necessary.
- Continue Phase 4 only once Phase 3 is complete, committed/pushed, and clean. Do not skip dependency gates.
- Existing research rule below remains mandatory. User has already authorized adjusting ONLY SDK-required dependencies; keep Ultralytics 8.4.71, preserve torch/torchvision and GUI OpenCV unless a concrete resolver requirement proves otherwise, and avoid unrelated upgrades.

## Resume instructions

When continuing:

1. Read this file first.
2. Run `git status`.
3. Confirm the current branch and last commit.
4. Continue from **Next exact actions**.
5. Do not redo completed phases.

## EXTERNAL TECHNOLOGY RESEARCH RULE

Before implementing any phase depending on an external library, SDK, API, model provider, framework, or hosted service:

1. Research CURRENT official documentation first.
2. Prefer first-party official documentation, package registry, GitHub repository/releases, and model page.
3. Verify latest stable version, Python/runtime compatibility, current API signatures, supported input/output formats, authentication, hosted pricing/usage behavior, and deprecations/breaking changes.
4. Do not blindly follow plan versions/examples when current official sources disagree.
5. Do not upgrade a working dependency merely because a newer version exists; change versions only when required and compatibility is verified.
6. Record research date, official sources checked, verified version/API, differences from the plan, and resulting implementation decision in this log.
7. If docs are ambiguous, inspect installed package API or official source before implementation.
8. Never claim verification without actually checking.

## Phase 3 delivery blocker — 2026-10-08

Phase 3 implementation and all validation gates are COMPLETE. Delivery checkpoint is incomplete: push failed.

- Intended four files were committed locally with message `feat(ai): add Roboflow mushroom detection provider`.
- `git push origin feat/live-camera` failed with exit 128: `Could not resolve host: github.com`.
- Remote: https://github.com/smart-phset/phset-ai.git. Branch feat/live-camera is ahead of the locally recorded origin branch by two commits (Phase 2 and Phase 3). Remote state cannot be verified until network access is restored.
- Working tree was clean immediately after the failed push. Only this required blocker record now modifies CODEX_WORK_LOG.md. This edit documents a delivery failure, not a post-commit SHA-only update.
- No source/dependency changes after the validated Phase 3 commit. No Phase 4 implementation started.
- Next exact actions: restore GitHub DNS/network access in this execution environment; read this log and inspect Git; retry pushing the existing commits without recreating Phase 3. Verify remote tip. Reconcile this blocker-log change as normal Phase 4 work, record previous checkpoint SHA there, and then begin Phase 4. Do not claim a clean delivered checkpoint until push succeeds.


## Phase 4 — live provider integration

Status: COMPLETE (implementation/validation); checkpoint commit/push next.
Research date: 2026-10-08.

### Git reconciliation

- Read this entire log first. Inspected status, branch, recent log, status -sb and remotes before source edits.
- Previous checkpoint SHA: 335f67d547ca025e37562067ab80df78aa86ff0f (`feat(ai): add Roboflow mushroom detection provider`). User successfully pushed it from their terminal.
- Local HEAD and recorded origin/feat/live-camera match that SHA; merge-base ancestry checks confirm both Phase 2 f2aaf30 and Phase 3 are contained in origin/feat/live-camera. Only the expected blocker work-log modification existed.
- Direct `git ls-remote` from this execution environment still fails GitHub DNS, so current remote verification is limited to the updated origin reference and user-confirmed push. Historical Phase 3 delivery-blocker section above is resolved by that push, preserved as history. Its existing modification is included in normal Phase 4 work; no standalone log commit.

### Research performed / decisions

- Reviewed integration plan, entire live_camera.py, detector contracts/providers, BackendPublisher and all existing camera/publisher tests. Reused verified installed SDK 1.7.3 API and official source research recorded above; no SDK changes needed.
- https://docs.python.org/3.11/library/concurrent.futures.html checked current Python 3.11 docs: Future.done enables nonblocking collection; result rethrows worker errors; shutdown(cancel_futures=True) cancels queued work but waits for running work. Preserve one worker and never submit while pending.
- https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html checked official current docs (redirect to 4.13.0): integer camera and stream URL inputs, read, release and set remain supported. Keep installed 4.10.0.84; no new capture API or upgrade required.
- SDK documentation URL now redirects; exact installed SDK behavior remains covered by Phase 3 installed-client mocked-transport tests. No new hosted pricing/version claim or live request made.
- Factory lazily imports hosted provider only when selected; local default requires no key/SDK. Remote validates key before model/camera use and requires no weights. New CLI selects local/roboflow and hosted model/endpoint; --imgsz exposes existing 416 default. Preserve conf/device/weights/fps/source/cam/reconnect/backend options, default FPS 5 and all thresholds/wording. Recommended hosted invocation explicitly uses --fps 1; do not change local defaults.
- Hosted DetectorUnavailableError yields GREY / Could not inspect, empty boxes/counts and unchanged backend schema; no exception details logged, no fallback, no camera reconnect. Subsequent requests follow existing schedule; frames while busy are dropped. Unexpected programming errors and local inference failures retain existing propagation.
- Hosted successful detections expire after max(5 seconds, two requested inference intervals), measured from frame submission, including delayed results already stale on arrival. Expiry publishes GREY once through existing publisher. Local display persistence is unchanged. No new stale timestamp presented as a successful inspection.
- Detector close now runs after executor shutdown alongside existing camera/window/publisher cleanup. Hosted worker shutdown still waits for the provider's existing bounded async deadline; synchronous encoding/capture calls are not preemptible.

### Files / dependency changes

Created: tests/test_live_providers.py (10 mocked integration/factory tests).
Modified: live_camera.py; CODEX_WORK_LOG.md (including preserved blocker reconciliation).
Dependency/version changes: NONE.
Intentionally unchanged: BackendPublisher, Spring backend/schema, ESP32/webcam capture/reconnect/buffer setting, local provider, Roboflow provider, models/best.pt, severity thresholds, existing verdict wording, protected packages, existing tests.

### Validation results

- `.venv/bin/python -m unittest discover -s tests -p test_live_providers.py -q`: PASS 10 tests, 0.072s.
- `.venv/bin/python -m unittest discover -s tests -q`: PASS 62 tests, 1.407s (all prior 52 retained).
- `.venv/bin/python -m compileall -q detectors tests live_camera.py backend_publisher.py bridge.py`: PASS.
- `git diff --check`: PASS (rerun after final log edit before staging).
- `UV_CACHE_DIR=/tmp/smartphset-uv-cache uv pip check --python .venv/bin/python`: PASS 58 compatible packages.
- Imports inference_sdk/numpy/requests/ultralytics/torch/torchvision/cv2: PASS.
- Installed: inference-sdk 1.7.3, numpy 2.3.5, requests 2.34.2, ultralytics 8.4.71, torch 2.12.1+cpu, torchvision 0.27.1+cpu, opencv-python 4.10.0.84.
- Coverage: local default/explicit and no hosted imports/key; hosted configuration without weights; missing key; CLI validation; exact provider/backend payload equivalence; failure GREY + scheduled recovery/no reconnect; one pending inference; stale/slow successful results; real camera read-failure reconnect; q and Ctrl+C resource cleanup. No live/paid requests.

### Known issues / next exact actions

- No hardware GUI/ESP32 or real hosted/backend manual test performed; acceptance with real grow-room imagery remains later manual validation/evaluation. Direct GitHub DNS in this tool environment remains unavailable as of reconciliation; attempt push after commit and record actual result.
- Current Git intended changes: M CODEX_WORK_LOG.md, M live_camera.py, ?? tests/test_live_providers.py. Branch feat/live-camera; previous checkpoint SHA above. Stage ONLY those three files after reviewing diff/status.
- Exact commit message: `feat(camera): add selectable AI detection providers`.
- Commit automatically after passing gates, push origin feat/live-camera, verify remote and clean tree. Do not edit log solely for own SHA.
- If push fails, preserve local commit and document delivery blocker; do not begin Phase 5.
- Next phase: Phase 5 — evaluation tooling. At its start read log/Git and record Phase 4 SHA; review plan evaluation requirements, implement tools/evaluate_detector.py and mocked tests for CSV, expected-vs-predicted results and latency metrics. No Phase 5 work in this checkpoint.


## Phase 4 delivery blocker — 2026-10-08

Implementation/validation COMPLETE; delivery checkpoint INCOMPLETE.

- Committed exactly live_camera.py, tests/test_live_providers.py, CODEX_WORK_LOG.md with `feat(camera): add selectable AI detection providers`.
- `git push origin feat/live-camera` failed exit 128: `Could not resolve host: github.com` from this execution environment. No successful push claimed.
- Working tree clean immediately after commit; this required failure-state record is the only subsequent modification. No source changes after commit and no Phase 5 work.
- Next exact actions: restore GitHub access for this environment or push existing feat/live-camera from the normal terminal; then reconcile Git and this preserved log modification as normal next-phase work, without a standalone log-only commit. Verify Phase 4 exists on origin before starting Phase 5. Never recreate completed integration.


## Phase 5 — detector evaluation tooling

Status: COMPLETE (implementation and validation). Delivery commit/push pending.

### Phase 4 reconciliation

- Read complete work log before edits; inspected git status, branch, log -10, status -sb, remote -v and full pre-existing work-log diff.
- Verified HEAD and recorded origin/feat/live-camera are bb81eca2f148681ea782b11d9925ffeac357be8a (`feat(camera): add selectable AI detection providers`); merge-base ancestry check passed. User confirmed successful external push. Only expected CODEX_WORK_LOG.md push-blocker note was modified before Phase 5.
- Preserve historical Phase 4 blocker note above, now resolved by user's external push and matching origin reference. Reconciliation is included here as normal Phase 5 work, never a standalone log commit. No independent fresh remote request is claimed.

### Research performed (2026-10-08)

- Reviewed actual detector contracts/providers, verdict function/factory, installed OpenCV API, existing test suite, plan evaluation section and .gitignore before implementation.
- https://docs.opencv.org/4.x/d4/da8/group__imgcodecs.html (current official page redirects to 4.13.0): imread accepts filename/flags, color decode is BGR, unreadable data returns empty output. Verified installed cv2 4.10.0 exposes imread(filename[, flags]); use existing IMREAD_COLOR, not a newer-only flag. Real temporary PNG fixture decoded successfully in test. No upgrade needed.
- https://docs.python.org/3.11/library/csv.html: DictWriter with explicit fieldnames and newline='' for CSV output.
- https://docs.python.org/3.11/library/statistics.html: mean for successful latencies. Chose explicitly documented nearest-rank p95 instead of quantiles interpolation/extrapolation for small datasets; handles singleton and zero samples deterministically.
- No new SDK/API/auth changes: reuse Phase 3 installed SDK 1.7.3 verification and existing provider. No live requests, pricing or model-quality verification in this phase. Existing dependency versions remain fixed; no new dependency requires latest-release selection.

### Implementation decisions / scoring policy

- tools/evaluate_detector.py supports script and module execution, --dataset/--data, --output CSV, --model-provider local|roboflow and existing weights/conf/imgsz/device/model-ID/API-URL configuration. Reuses build_detector and summarize_detections, never duplicates provider inference or verdict thresholds.
- Require all three labeled category directories; recursive discovery within them, deterministic relative-path sort. Explicit case-insensitive JPG/JPEG/PNG/BMP/TIF/TIFF/WEBP only. CSV can never be discovered as an image. Missing directories are clear configuration failures. Empty complete dataset emits null metrics and header-only CSV without loading provider.
- Sequential detect once per readable image, no concurrent calls, queues or application retries; SDK internal retries remain. Detector closes in finally. Hosted evaluation uses existing environment key and can incur hosted usage when explicitly invoked on real images.
- Contaminated correct ONLY for contamination_suspected with RED/AMBER. GREY contamination counts as a miss and a distinct low_confidence_contamination_miss. Other contaminated outcomes are misses. Healthy correct ONLY no_contamination_seen/GREEN; any contamination verdict is a healthy false alert. Negative correct ONLY no_detection/GREY; Healthy GREEN is a false claim and any contamination verdict is a negative contamination false alert, including low-confidence GREY.
- Errors/unreadable/malformed output remain GREY/unavailable, blank correctness/latency, excluded from accuracy/latency and successful miss/false-alert counts. Availability is separately prominent; unavailable contaminated images must be reviewed in addition to misses. Validate normalized boxes/finite confidence/coordinates/latency before verdict calculation so malformed output cannot generate fake GREEN.
- Report counts, accuracy among successful inspections, misses, low-confidence misses, healthy false alerts, negative false claims/contamination alerts, successful no_detection count, mean latency and nearest-rank p95. No samples -> null accuracy/latencies. Provider timing excludes file decode and includes provider work; no warmup exclusion. Detailed CSV retains unrounded confidence and provider/model identity. Exception text omitted to prevent accidental secret leakage.
- .gitignore already ignores *.csv; verified git check-ignore evaluation-results-local.csv. No ignore change or generated output committed.
- Plan example uses --provider/--model-id; final tool follows user's required --model-provider/--roboflow-model-id shared live configuration, with --data retained as dataset alias.

### Files created / modified

Created: tools/evaluate_detector.py; tests/test_evaluate_detector.py; docs/evaluation.md (commands, exact scoring and statistical definitions/limitations).
Modified: CODEX_WORK_LOG.md, including preserved Phase 4 blocker reconciliation.
Dependency/version changes: NONE. Camera, BackendPublisher/backend, provider implementations, models/best.pt, verdict thresholds, existing tests and .gitignore intentionally unchanged. No training/frontend/backend work.

### Tests / compatibility results

- `.venv/bin/python -m unittest discover -s tests -p test_evaluate_detector.py -q`: PASS 19 tests, 0.071s.
- `.venv/bin/python -m unittest discover -s tests -q`: PASS 81 tests, 1.282s (all previous 62 retained).
- `.venv/bin/python -m compileall -q tools tests detectors live_camera.py backend_publisher.py bridge.py`: PASS.
- `git diff --check`: PASS; rerun on completed log before staging.
- `UV_CACHE_DIR=/tmp/smartphset-uv-cache uv pip check --python .venv/bin/python`: PASS, 58 compatible packages.
- `.venv/bin/python tools/evaluate_detector.py --help`: PASS, no model/key/network needed.
- Safe fixture CLI test: temporary actual PNG written/read by installed cv2, local detector mocked, CSV correct=True verified and detector closed. Empty dataset fixture also verified no provider construction. No real local inference or live hosted request.
- Test coverage: discovery/determinism/extensions, required folders, all requested scoring outcomes, low-confidence miss, unknown labels, safe provider failure/continuation, unreadable/invalid result, mean and p95 incl singleton/empty, CSV schema/precision, local/hosted factory selection and CLI/cleanup. Socket connection blocked in evaluation tests.

### Known issues / real data / current state

- No evaluation/ directory or real evaluation images exist in repository. No real dataset evaluated and no model-quality metrics manufactured. Synthetic tests demonstrate implementation correctness only. Image-level scoring is not box-level mAP or production acceptance; representative held-out data is required. Confidence filtering may remove boxes upstream; compare providers under documented identical settings.
- Current branch feat/live-camera; previous SHA bb81eca2f148681ea782b11d9925ffeac357be8a. Intended status: M CODEX_WORK_LOG.md; ?? tools/evaluate_detector.py; ?? tests/test_evaluate_detector.py; ?? docs/evaluation.md. All validation passed; no implementation blockers.
- GitHub DNS has failed in prior tool sessions despite successful external pushes. Attempt normal push after commit; record actual result and do not start Phase 6 on failure.

### Exact commit / next actions

1. Review intended full diff/status, stage ONLY tools/evaluate_detector.py, tests/test_evaluate_detector.py, docs/evaluation.md, CODEX_WORK_LOG.md.
2. Commit `feat(ai): add detector evaluation workflow`; push origin feat/live-camera; verify push and clean Git. Report SHA in chat, no post-commit SHA-only edit.
3. If push fails, preserve validated local commit and record delivery blocker. Wait for network/external push before Phase 6.
4. Phase 6 — documentation and final validation: reconcile Git/previous SHA; update docs/live-camera.md for webcam/local, ESP32/local, ESP32/Roboflow, keys, failures, throttling and cleanup. Create docs/model-integration.md with model/source/classes/CC BY 4.0 attribution, current deployment/confidence, evaluation procedure/results explicitly not yet measured. Link evaluator documentation from README as useful; no accuracy claims without real data.
5. Run final full tests, syntax, CLI help/diff/uv compatibility gates and provide manual camera/backend/evaluation commands. Do not invoke real paid inference without a separately intentional manual run. Phase 6 not started in this checkpoint.
