# SmartPhset AI — Codex Work Log

## Current status

Status: IN_PROGRESS

Current branch:
`feat/live-camera`

Last verified commit:
`f2aaf30e8a3b1f832f32a156dc798c7f879c173d`

Last updated:
`2026-10-08T16:47:19+07:00`

## Goal

Integrate the existing oyster mushroom contamination model into SmartPhset AI
while preserving local-model support, ESP32-CAM streaming, backend publishing,
and SmartPhset verdict behavior.

## Completed phases

- [x] Phase 0 — repository inspection
- [x] Phase 1 — detector abstractions
- [x] Phase 2 — local Ultralytics provider
- [x] Phase 3 — Roboflow provider
- [ ] Phase 4 — live-camera integration
- [ ] Phase 5 — evaluation tooling
- [ ] Phase 6 — documentation and final validation

## Current phase

Phase 3 — Roboflow provider COMPLETE. All installation/API/test/compatibility gates passed. Phase 4 NOT started; begin only after successful commit/push and clean tree.

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
