# Real camera → frontend acceptance

Status: LIVE ESP32-CAM AI INTEGRATION PATH VERIFIED; frontend visual acceptance PENDING.
REAL MUSHROOM RECOGNITION DEFERRED / NOT VERIFIED: no real mushrooms available.
The current checkpoint below supersedes historical camera-preparation instructions.
No camera, hosted inference or database publishing is performed by automated checks.
Use the existing virtual environment and private configuration. Do not overwrite
frontend `.env.local` or recreate databases/volumes.

## Current real ESP32-CAM checkpoint — 2026-10-10

User observed the real network stream, real frame acquisition, local YOLO inference,
BackendPublisher -> Spring ingestion -> PostgreSQL persistence and successful latest
retrieval. This is supplied acceptance evidence, not a new Codex runtime run.
No_detection proves the completed integration path; it does not prove mushroom
classification, disease recognition or model precision/recall/accuracy.

Exact persisted record:

```json
{
  "id": "f6b21953-f0b5-4054-8665-cbfe78d7a7da",
  "event_id": "7cf56612-46a1-46a9-9fb4-885c59c6b87c",
  "camera_id": "esp32-cam",
  "captured_at": "2026-10-10T11:17:49.137417Z",
  "verdict": "no_detection",
  "severity": "GREY",
  "message": "Could not inspect",
  "n_contaminated": 0,
  "n_healthy": 0,
  "max_conf": 0.0,
  "max_contaminated_conf": 0.0,
  "width": 640,
  "height": 480,
  "inference_ms": 84,
  "created_at": "2026-10-10T11:17:49.267701Z",
  "boxes": []
}
```

### Remaining browser acceptance commands

Preserve private .env.local and change only the camera setting if needed:
`SMARTPHSET_AI_CAMERA_ID=esp32-cam`. Retain the existing backend URL and private
login/IoT configuration. Restart Next after changing configuration. No AI ingest
key is required for these read endpoints. Do not assume services survived closure;
if Spring/PostgreSQL are stopped, use the existing private configuration and
startup sections below. Do not recreate databases or publish synthetic records.

Read backend latest/history in a normal local terminal:

```bash
curl -fsS 'http://localhost:9090/api/ai/detections/latest?camera=esp32-cam' | python3 -m json.tool
curl -fsS 'http://localhost:9090/api/ai/detections?camera=esp32-cam&limit=100' | python3 -m json.tool
```

Start Next in a separate terminal (stop an old Next instance first if necessary):

```bash
cd /home/ratanak/smart-phset/SmartPhset-Prototype-Frontend
npm run dev -- --port 3000
```

Sign in at http://localhost:3000 using the existing private login. Open these in
that SAME authenticated browser:

- http://localhost:3000/api/monitoring/detection — {cameraId,detection}.
- http://localhost:3000/api/monitoring/detections — {cameraId,detections}, latest 20.
- http://localhost:3000/ — Overview, AI / Mushroom Health section.
- http://localhost:3000/history — Detection history.

For readable JSON without copying session cookies/secrets, run this in browser
DevTools Console while signed in at localhost:3000:

```javascript
for (const path of ['/api/monitoring/detection', '/api/monitoring/detections']) {
  const response = await fetch(path, { cache: 'no-store', credentials: 'same-origin' });
  console.log(path, response.status, await response.json());
}
```

Unauthenticated terminal curl to Next returns 401; use the browser session above.
Compare id f6b21953-f0b5-4054-8665-cbfe78d7a7da, camera_id esp32-cam,
captured_at 2026-10-10T11:17:49.137417Z, created_at
2026-10-10T11:17:49.267701Z, verdict no_detection, severity GREY, message
Could not inspect, both counts zero and both raw confidences 0.0 in Next JSON.
Spring also exposes dimensions 640x480, inference_ms 84, event_id and boxes=[];
the current frontend parser intentionally excludes these fields.

Overview should show esp32-cam, Could not inspect, matching capture time,
0 healthy / 0 flagged and Unavailable for both confidence summaries. History shows
Could not inspect, GREY and Unavailable contamination confidence. IDs are not printed
on the cards: use JSON to establish identity, then compare visible fields. The UI
formats browser-local time; in Asia/Phnom_Penh capture time is 18:17:49 on
2026-10-10, with microseconds available only in JSON.

If inference continues, newer snapshots can replace latest and eventually move
this record out of the latest 20. Stop the camera normally to avoid further snapshots;
re-read latest/history. Do not alter timestamps, delete records or repost this
record to force it to the top. If this target is already outside frontend history,
report that condition before changing the acceptance target; current frontend has
no record-by-ID page or selectable history limit.

Frontend live-AI acceptance stays PENDING until the user confirms the matching
record in the browser. Then finalize documentation and create/push a NEW AI
checkpoint commit; do not amend c2b8b00 or merge frontend into main.

Real mushroom detection/classification/disease/model-quality acceptance is deferred
because no real mushrooms are available. Actual water pump/load, physical fan/light,
real soil sensor/calibration/telemetry and remaining actuator safety remain deferred.
Floating GPIO34 values are invalid soil measurements. The relay switching evidence
does not establish actual pump/load operation.

## Historical preparation / optional future runs

The sections below preserve the previous audit and reproducible startup examples.
Webcam examples are alternatives, not the source of the verified ESP32-CAM result;
use esp32-cam for the current remaining acceptance and defer mushroom testing.

## Audited flow

`live_camera.py` opens OpenCV webcam `--cam N` or a network stream `--source URL`.
Webcam IDs are `webcam-N`; all network sources use `esp32-cam`. Source takes
precedence over webcam. No configurable independent camera ID exists in this CLI.
Neither available camera hardware nor an ESP32-CAM stream address is assumed here.

Local (default) uses `models/best.pt`, Ultralytics YOLO loaded once, and BGR frames.
Roboflow uses the official SDK, in-memory selected frames, `ROBOFLOW_API_KEY` via
header authentication, model `contamination-detection-ozkwx/1`, and an eight-second
async deadline. No fallback to local. Start hosted mode at `--fps 1`; it uploads
images to the hosted provider and may incur usage. Spring receives JSON only.

One inference worker drops busy frames. Normalized labels are lowercase; the shared
verdict policy gives contamination priority: >=0.80 RED, >=0.40 AMBER, otherwise
GREY. Healthy without contamination gives GREEN. No recognized detections gives
`no_detection`/GREY, not healthy. Hosted failures/expired results also give GREY;
those do not prove successful inference. Successful timestamps are generated at
inference start, not a hardware camera timestamp. Preview shows verdict/counts/
confidence/latency. The scheduler exposes no per-inference terminal success log.

BackendPublisher offers the first completed inspection, then every five seconds
or verdict/severity change. One HTTP worker and one replaceable pending snapshot;
three-second request timeout, failed snapshots dropped, no publisher retries or
durable queue. Network capture reconnects; a webcam read failure stops inspection.
Hosted inference retries on the normal schedule (SDK internal retries also exist).
q/Ctrl+C cleans up; shutdown can discard pending publishing work.

### Exact Spring contract

POST `/api/ai/detections`, `Content-Type: application/json`.
Python `SMARTPHSET_AI_INGEST_KEY` supplies `X-SmartPhset-AI-Key` if nonempty.
Spring `AI_INGEST_KEY` configures the expected value. Nonblank Spring key requires
an exact matching header (missing/wrong →401). Blank/unset Spring key permits
ingestion from any reachable caller, not just loopback. GETs are public and require
neither the AI key nor IoT key. The existing narrow CSRF exemption applies to POST.

Request fields, generated from actual inference (do not manually post fixtures):

| Field | Existing representation |
| --- | --- |
| event_id | Newly generated UUID per offered snapshot |
| camera_id | webcam-N or esp32-cam, 1–100 characters |
| captured_at | UTC ISO timestamp |
| verdict | contamination_suspected / no_contamination_seen / no_detection / camera_error |
| severity | RED / AMBER / GREEN / GREY, must match summary |
| message | Verdict message, max 255 characters |
| n_contaminated, n_healthy | Nonnegative integer counts |
| max_conf, max_contaminated_conf | Unrounded finite confidence, 0–1 |
| width, height | Positive frame dimensions |
| inference_ms | Rounded nonnegative integer latency |
| boxes | Array of label, conf (0–1), xyxy (four integers in frame bounds) |

First POST201; duplicate valid event UUID returns200 and the original persisted
record. Invalid input400 `{error:"invalid_detection",message:...}`. Ingestion
uses a transaction/advisory lock, `ai_scans` plus associated `ai_detection_boxes`.
After flush, refresh returns database-canonical timestamps (PostgreSQL microseconds,
so a Python timestamp can round). Response adds `id` and `created_at` to request
fields. No inference images stored by this API.

Latest GET `/api/ai/detections/latest?camera=webcam-0`:200 record or404
`{error:"detection_not_found",message:"No detection for camera"}`.
History GET `/api/ai/detections?camera=webcam-0&limit=20`: array, possibly empty;
limit1–100, ordered captured_at/created_at/id descending, filtered by camera.

Frontend `/` and `/climate` poll authenticated Next GET
`/api/monitoring/detection`; `/history` polls `/api/monitoring/detections`.
Next forwards to these Spring GETs using server `SMARTPHSET_API_BASE_URL` and
`SMARTPHSET_AI_CAMERA_ID`; sends no AI or IoT key to AI reads. Browser receives
selected real DTO fields (including persisted id, camera, timestamps, verdict and
confidence), not images or event_id. No mocked result fallback. Loading, no-result
404 and backend errors are explicit. Old retrieved results are labelled on errors;
the AI card is explicitly a stored result, not a camera-online heartbeat.
GREY/no_detection/camera_error display unavailable confidence, not healthy.
Overview exposes both confidence summaries; history shows contamination confidence.

## Terminal 1 — containers

```bash
cd /home/ratanak/smart-phset/api
docker compose up -d postgres mosquitto
docker compose ps
```

Retain existing Compose private settings. Mosquitto supports simultaneous IoT
monitoring; AI transport itself uses HTTP and PostgreSQL, not MQTT.

## Terminal 2 — Spring

Reuse existing private DB, MQTT and IoT settings. Enter the same AI ingest key
again in Terminal 3; it is not the IoT key.

```bash
cd /home/ratanak/smart-phset/api
export JAVA_HOME=/opt/android-studio/jbr
export PATH="$JAVA_HOME/bin:$PATH"
export DB_URL=jdbc:postgresql://localhost:5432/smartphset
export DB_USERNAME=smartphset
read -rsp 'Existing DB password: ' DB_PASSWORD; printf '\n'
export DB_PASSWORD
read -rsp 'Existing IoT key: ' IOT_API_KEY; printf '\n'
export IOT_API_KEY
read -rsp 'AI ingest key (reuse configured value): ' AI_INGEST_KEY; printf '\n'
export AI_INGEST_KEY
export MQTT_ENABLED=true
export MQTT_BROKER_URL=tcp://localhost:1883
export MQTT_DEVICES=grow-room-1
./gradlew test --tests '*AiDetection*'
./gradlew bootRun
```

Use your actual DB username/URL if different. Blank AI input selects existing open
development mode; do not mistake that for authenticated ingestion. Preserve any
configured MQTT credentials privately. Wait for successful Spring/Flyway startup.

Before camera start, inspect latest/history to identify existing records:

```bash
curl -sS -i 'http://localhost:9090/api/ai/detections/latest?camera=webcam-0'
curl -fsS 'http://localhost:9090/api/ai/detections?camera=webcam-0&limit=20' | python3 -m json.tool
```

These GETs can run in Terminal 1 after containers start. Existing results alone
cannot prove this new camera session. Do not run synthetic opt-in publisher tests
as live camera acceptance; they intentionally write fixture records.

## Terminal 3 — live local webcam

Use a graphical desktop and show real mushroom bags to the camera. Webcam0 is
the simplest supported first attempt; successful hardware access remains manual.

```bash
cd /home/ratanak/smart-phset/SmartPhset-AI
read -rsp 'Matching Spring AI ingest key: ' SMARTPHSET_AI_INGEST_KEY; printf '\n'
export SMARTPHSET_AI_INGEST_KEY
export SMARTPHSET_BACKEND_URL=http://localhost:9090
QT_QPA_PLATFORM=xcb .venv/bin/python live_camera.py \
  --cam 0 --model-provider local --device cpu \
  --conf 0.4 --fps 5 --publish-every 5
```

Expected startup: `Loading YOLO model: .../models/best.pt`,
`Opening local camera: 0`, `Video source opened: webcam-0`,
`SmartPhset Live AI running.` These confirm startup only. The preview must show
actual changing frames and completed inference (latency/FPS/age), then a real
verdict. Even no_detection after a successful local inference is an honest result;
it proves transport, not disease recognition or model quality.

There is **no successful-publish log line** in current BackendPublisher.
`Backend publish failed: ...` reports failure; absence of that line is insufficient
proof. The new matching record in Spring GET/history is the delivery evidence.
Do not quit until you see that record; close can discard an unsent snapshot.

ESP32-CAM alternative: replace `--cam 0` with
`--source "http://<actual-camera-ip>:81/stream"`, only after checking the real
firmware's stream URL. Camera ID becomes `esp32-cam`; use that in GETs/frontend.
This is a camera device, not the GPIO27 relay-control ESP32 by assumption.
If webcam0 fails, inspect actual webcam indices or provide a working stream URL;
no camera subsystem rewrite is required to select an existing source.

Optional hosted alternative uses the same camera flags, but replace provider
with `--model-provider roboflow --fps 1` (remove local `--fps 5`), set
`ROBOFLOW_API_KEY` privately, and keep the existing model ID/API URL defaults.
Do not treat provider-unavailable GREY as a successful hosted inference.

## Terminal 4 — Next.js

Preserve existing ignored `.env.local` login/IoT settings. Privately set:

```dotenv
SMARTPHSET_API_BASE_URL=http://localhost:9090
SMARTPHSET_AI_CAMERA_ID=esp32-cam
```

Keep existing server-only `SMARTPHSET_IOT_API_KEY`, `SMARTPHSET_DEVICE_ID`,
`AUTH_USER`, `AUTH_PASSWORD`, `AUTH_SECRET` and guest policy. No AI ingest or
Roboflow secret is needed in Next; never add public secret variables. Restart Next
after a camera-ID configuration change.

```bash
cd /home/ratanak/smart-phset/SmartPhset-Prototype-Frontend
npm run dev
```

Open http://localhost:3000, sign in, view **AI / Mushroom Health** on Overview;
http://localhost:3000/history shows the latest20 real stored results.

## Exact acceptance evidence

1. Record local session start time; inspect pre-existing latest/history first.
2. Observe real changing camera frames and completed local inference preview.
   Record the actual verdict/level/counts; do not stage a desired disease result.
3. While camera runs, inspect Spring latest/history for the selected camera.
   Require a captured_at after session start, new persisted id/event_id and real
   dimensions/inference_ms/boxes. Changing created_at alone is insufficient.
4. After a new record appears, press q to stop camera and allow pending HTTP work
   to settle. Re-read latest so comparisons do not race continuing snapshots.
5. In the signed-in browser open `/api/monitoring/detection` and
   `/api/monitoring/detections`. Compare detection.id, camera_id, captured_at,
   created_at, verdict, severity, counts and both confidence summaries to Spring.
   Latest must also appear in history. Persisted IDs distinguish matching records.
6. Overview must display the same camera/capture time/result/counts and confidence
   (percent with one decimal; raw0.81234 displays81.2%). Display times are browser
   local time; compare raw ISO timestamps in JSON, including database rounding.
   GREY/no_detection shows unavailable confidence instead of implying health.
7. Optionally inspect persisted rows read-only, with existing Compose DB identity:

```bash
cd /home/ratanak/smart-phset/api
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SELECT id, event_id, camera_id, captured_at, created_at, verdict, severity,
       max_conf, max_contaminated_conf, width, height, inference_ms
FROM ai_scans WHERE camera_id = 'webcam-0'
ORDER BY captured_at DESC, created_at DESC, id DESC LIMIT 3;
SQL
```

For ESP32 use esp32-cam in SQL. No credentials are printed. Never delete records
or fabricate an input to force a GREEN/RED card.

Report camera/provider, observed preview verdict, new persisted id/capture time,
raw confidences and matching browser result. Live AI acceptance remains pending
until the user reports the real result visible in the frontend. This does not
verify model accuracy, actual water pump/load, fan/light or soil hardware.
