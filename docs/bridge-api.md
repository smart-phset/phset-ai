# Bridge API

`bridge.py` is a small HTTP server (Python standard library). Default address `http://<host>:8000`.

## Authentication

When started with `--api-key` (or `BRIDGE_API_KEY`), **every** request needs one of:
- the header `Authorization: Bearer <key>`, or
- the query parameter `?key=<key>` (used by the status page in a browser).

Otherwise the reply is `401 {"error": "unauthorized"}`. Without a key, the bridge is open to anyone who can reach
it, so only do that on your own Wi-Fi.

## POST /image

Check one photo.

- **Query:** `camera=<id>` (optional, default `cam1`; letters, digits, `_` and `-`, up to 40 characters).
- **Body:** raw JPEG bytes. Header `Content-Type: image/jpeg`.

**Reply 200:**

```json
{
 "time": "2026-10-05T18:30:12",
 "camera": "phone-1",
 "verdict": "contamination_suspected",
 "message": "Possible mould on phone-1: check and isolate the bag.",
 "n_contaminated": 1,
 "n_healthy": 3,
 "max_conf": 0.94,
 "max_contaminated_conf": 0.94,
 "width": 1280,
 "height": 960,
 "ms": 180,
 "image": "<path on the laptop of the annotated photo>",
 "boxes": [{"label": "contaminated", "conf": 0.94, "xyxy": [412, 220, 690, 610]}]
}
```

The values above are an example of the shape, not a real result.

| Field | Meaning |
|---|---|
| `verdict` | `contamination_suspected`, `no_contamination_seen`, `no_detection` (no bag recognised) or `camera_error` (image missing or unreadable) |
| `max_contaminated_conf` | Highest confidence among **contaminated** boxes, 0 if none. **Use this for the alert level.** |
| `max_conf` | Highest confidence of any box, healthy included. Do not use it for alerts. |
| `n_contaminated`, `n_healthy` | Number of boxes of each class |
| `boxes` | Each box: `label` (`contaminated` or `healthy`), `conf`, `xyxy` = left, top, right, bottom in pixels of the original photo |
| `width`, `height` | Size of the photo in pixels |
| `ms` | Time the model took |
| `image` | Local file path of the annotated copy. Internal; do not show it to users. |

`camera_error` and `no_detection` mean "inspection unavailable", **never** healthy.

The model reports boxes from confidence 0.40 up (`--conf`). Every checked photo is saved in `bridge_log/images/`
(raw and annotated) and logged in `bridge_log/vision.csv`.

## POST /telemetry

Optional climate log, for an ESP32 that talks to the bridge directly. The Node backend normally handles readings
instead.

- **Body (JSON):** `{"device": "esp32-1", "temp_c": 27.1, "rh": 88.5}` plus any extra fields
  (`co2_ppm`, `mist_on`, `fan_on`, `water_ok`, `fault`, or others, which are kept in an `extra` column).
- **Reply:** `{"ok": true, "time": "..."}`, or `400` if `temp_c` or `rh` are not numbers.
- Logged to `bridge_log/telemetry_<device>.csv`. The bridge only logs; it never switches the fan or mister.

## GET /status

The latest reading per device and the latest result per camera:

```json
{"telemetry": {"esp32-1": {"temp_c": 27.1, "rh": 88.5, "age_s": 12, "stale": false}},
 "vision": {"phone-1": {"verdict": "no_contamination_seen", "age_s": 40, "stale": false}}}
```

- A camera is `stale` after no new photo for 3 times `--every` (at least 180 s). Its verdict then reads `STALE`.
- A device is `stale` after 120 s without a reading.

## Other routes

| Route | What it returns |
|---|---|
| `GET /latest.jpg?camera=<id>` | The last annotated photo for that camera (JPEG), or 404 |
| `GET /` | The human status page with an upload box (auto-refreshes) |

## Errors

`401` unauthorized, `400` bad telemetry, `404` unknown path, `500 {"ok": false, "error": "..."}` on an internal
error.
