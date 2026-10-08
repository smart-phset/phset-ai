# AI to Spring integration verification

Backend checkout is `phset-api` (workspace directory `api/`). Its actual routes:

- POST `/api/ai/detections`
- GET `/api/ai/detections/latest?camera=...`
- GET `/api/ai/detections?camera=...&limit=20` (no `/history` suffix)

Default port is 9090. No AI schema rename is required: JSON uses `event_id`,
`camera_id`, `captured_at`, `verdict`, `severity`, `message`, counts/confidence
maxima, `width`, `height`, `inference_ms`, and `boxes` with `label`, `conf` and
four integer `xyxy` coordinates. Both repositories carry the same golden
`ai-detection.json` test fixture. The Python contract test generates it through
actual verdict/payload code; Spring validates/deserializes the same document.

Backend requires ordered boxes within frame dimensions, confidences in [0,1],
nonnegative counts/latency, valid verdict/severity combinations and timestamps.
Provider coordinates are converted to integers by the existing publisher; the
publisher does not clip coordinates. If a provider returns out-of-frame coordinates,
Spring rejects that event; it is dropped safely by the best-effort publisher.
No clipping or backend-validation weakening is introduced here without a proven
runtime need. Counts/boxes summary consistency beyond current backend validations
is not strengthened in this stage.

Spring Security currently permits detection routes and exempts machine POST from
CSRF; unrelated routes remain authenticated. Controller checks optional
`AI_INGEST_KEY` (`app.ai.ingest-key`); AI sends matching
`SMARTPHSET_AI_INGEST_KEY` as `X-SmartPhset-AI-Key`. If configured, missing/wrong key
returns 401; valid key is accepted. Blank/unset key allows ingest, with no network
origin restriction: use only isolated local development, or configure a key before
exposing the service. GET routes are currently public. Do not globally disable
security to work around a 403; check exact route, active configuration and running
backend version. The narrow CSRF exemption and ingest authentication are covered
by backend tests and the normal-environment runtime acceptance.

Flyway V3 defines ai_scans and ai_detection_boxes with FK/cascade, unique event_id,
TIMESTAMPTZ and confidence/coordinate storage. First valid event is 201; duplicate
is 200 with original data. The initial response refreshes the saved managed entity
from PostgreSQL before mapping: first and duplicate bodies use the same canonical
persisted timestamps, including PostgreSQL microsecond rounding. Transaction advisory locking serializes duplicate event
IDs, and database uniqueness is the backstop. Latest/history order by captured_at,
created_at, then UUID descending, scoped to camera; limit 1–100. Applied migrations
are preserved. Publisher itself drops failed events rather than retrying; replaying
the same payload/event ID remains idempotent.

## Run in a normal environment

Use a test database/backend, not production: acceptance leaves uniquely named
`phase7-<uuid>` synthetic records. No camera/model/Roboflow request is needed.

1. In phset-api, use Java 25 and accessible Docker, then run `./gradlew test`
   and `./gradlew build`. Testcontainers provisions PostgreSQL 18 for tests.
2. Start your configured local PostgreSQL and backend. From backend root:
   `docker compose up -d postgres`, configure DB_URL/DB_USERNAME/DB_PASSWORD and
   optional AI_INGEST_KEY privately, then `./gradlew bootRun`. This uses the local
   development database. Do not print/source secrets into logs.
3. From SmartPhset-AI with installed requirements and a matching ingest key:

```bash
export SMARTPHSET_INTEGRATION_BACKEND_URL='http://localhost:9090'
# Set SMARTPHSET_AI_INGEST_KEY privately if AI_INGEST_KEY is configured.
.venv/bin/python -m unittest discover -s tests \
  -p test_backend_live_integration.py -v
```

4. Repeat against a backend restarted with AI_INGEST_KEY unset and AI client key
   unset to verify the explicitly open local-development mode. The existing
   Testcontainers local-mode test covers that configuration too.
5. Run the full AI suite without the opt-in environment variable for isolated
   regressions. Existing publisher tests verify backend outage survival, bounded
   pending work and replacement of stale pending snapshots without preview waits.

The opt-in test checks actual POST/duplicate, timestamp/box round-trip, latest,
history/limit, configured missing/wrong keys, and actual background publisher
POST followed by retrieval. Assert failures must be investigated; never count a
skipped live test as end-to-end success. Backend tests additionally cover concurrent
duplicates, malformed values, camera isolation and deterministic ties.

## Current evidence

Phase 7 implementation and runtime acceptance are **complete**. In the normal
developer environment, focused backend tests, full tests and build passed. Spring
started on port 9090 against PostgreSQL 18.6; Flyway validated all three migrations
and confirmed current schema version 3. The actual BackendPublisher acceptance
test passed (1 test, 1.264s), covering persistence/boxes, identical first/duplicate
responses, latest/history and applicable ingest authentication. Backend regression
tests cover both configured-key and open local-development modes.

Codex inspected passing backend test reports and ran isolated AI regressions,
syntax/import/dependency checks. Codex cannot create localhost sockets/access
Docker, so real runtime validation was performed in the normal developer
environment. No ESP32 hardware acceptance or live Roboflow inference was performed.
Remote delivery is tracked separately in CODEX_WORK_LOG.md; Phase 8 waits for both
repository commits to be delivered.
