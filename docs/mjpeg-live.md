# Laptop live detection

The existing `live_camera.py` uses one OpenCV capture, an asynchronous inference
worker, `infer_detector`, `draw_overlay`, and `BackendPublisher`. Without
`--serve`, desktop preview behavior is retained.

Serving mode uses the same capture loop: capture, infer, annotate that exact
frame, encode JPEG at quality 80, replace a condition-protected latest frame,
and wait for the remainder of the configured FPS interval. Inference is
synchronous in this mode; there is no second capture or worker. Slow inference
limits actual FPS. HTTP consumers never capture or infer, and slow consumers
skip intermediate frames. `live_stream.py` uses the standard-library HTTP server
approach already in `bridge.py`; no new dependencies are required.

SIGINT/SIGTERM stops the producer/server, releases the camera, and closes the
publisher/detector. Browser disconnects close only that consumer. Camera failure
keeps health reachable with `camera_unavailable`; restore the camera and restart
the service. Model failures report `inference_unavailable`. No-detection frames
still stream. The existing `--source` option remains available for a later
network camera without any ESP32-specific UI.

Next.js session-protected Node routes forward the multipart stream incrementally
with no caching and upstream cancellation. The native browser image uses only
`/api/ai/live/stream`. Health and metadata poll separately every two seconds;
video is not polled. Metadata reuses the Spring monitoring adapter with an
explicit `webcam-0` override. Upload Image retains the existing workflow.

## Start

Add this new server-only variable to the frontend `.env.local`:

```dotenv
SMARTPHSET_AI_LIVE_BASE_URL=http://127.0.0.1:8001
```

Keep the existing `SMARTPHSET_API_BASE_URL=http://localhost:9090` and upload
backend configuration. Next.js must run on the laptop or be able to reach its AI
service: loopback on remote hosting does not refer to this laptop.
Export the existing `SMARTPHSET_AI_INGEST_KEY` in the AI terminal if Spring
requires it. Never put it into a public variable or stream URL.

With the existing Spring/PostgreSQL backend running:

```bash
cd /home/ratanak/smart-phset/SmartPhset-AI
QT_QPA_PLATFORM=xcb .venv/bin/python live_camera.py \
  --cam 0 --model-provider local --device cpu --conf 0.4 \
  --fps 5 --publish-every 5 --backend-url http://localhost:9090 \
  --serve --host 127.0.0.1 --port 8001
```

Serving mode is headless; the Qt variable is optional. In another terminal:

```bash
cd /home/ratanak/smart-phset/SmartPhset-Prototype-Frontend
npm run dev -- --hostname 127.0.0.1 --port 3100
```

- AI health: http://127.0.0.1:8001/health
- AI stream: http://127.0.0.1:8001/stream.mjpg
- Frontend: http://127.0.0.1:3100/scan
- Authenticated proxy health: http://127.0.0.1:3100/api/ai/live/health
- Authenticated proxy stream: http://127.0.0.1:3100/api/ai/live/stream

## Physical acceptance (not performed)

1. Close other camera apps. Start Spring, Python and Next.js. Check AI health:
   `camera: webcam-0`, `streaming: true`. Sign in or continue as a guest.
2. Open `/scan`, move something in front of the webcam, and confirm continuous
   motion. Network tools should show one long-lived MJPEG request.
3. Show a bag and inspect real model boxes/labels/confidence and saved Spring
   metadata. No particular detection is guaranteed. An empty model result must
   keep streaming and show No detection in metadata.
4. Open a second tab; close it and confirm the first still streams. Switch to
   Upload Image and upload a JPEG/PNG through the existing workflow, then switch
   back to Live Detection. Existing demo behavior applies if upload is unconfigured.
5. Stop Spring: video must continue while metadata becomes unavailable. Restart
   Spring and check recovery.
6. Stop Python: expect Live AI service is offline. Restart and check reconnection.
   Start with an unavailable webcam (or unplug a USB camera): expect Camera
   unavailable. Restore the camera and restart Python.
7. Ctrl+C Python and verify another camera application can open the webcam.

## Automated verification

AI: 91 tests run, one opt-in Spring/PostgreSQL test skipped; remaining tests pass.
New tests use fake capture/inference and never open /dev/video0.
Frontend: 20 assertions-as-tests across the two suites pass; lint/typecheck pass.
`git diff --check` passes in both repositories.

`npm run build` is blocked by Turbopack's helper port bind while processing
`globals.css`: Operation not permitted (OS error 1) in the sandbox. No production
configuration was changed to bypass it. A complete production build and built
client-bundle audit remain for a run outside the sandbox.

No backend, firmware, MQTT or actuator files were modified for this task.
No commit, push, or physical webcam acceptance was performed.
