#!/usr/bin/env python
"""
SmartPhset -- hardware bridge (prototype hub).

The one program the hardware talks to. It runs on the laptop now (later on the edge box,
e.g. an Orange Pi / Raspberry Pi) and joins the two loops:

  CLIMATE  ESP32 controller --POST /telemetry (JSON)--> bridge  (logs; control stays on the ESP32)
  VISION   camera --POST /image (JPEG)--> bridge --> AI model --> verdict JSON + saved images
           or the bridge pulls a snapshot itself: --poll http://<esp32-cam>/capture

Open http://<laptop-ip>:8000/ in any browser on the same Wi-Fi for a live status page
(it also has a photo upload box, so a plain phone can test the AI).

Run (from the repo folder, with the venv active; see docs/run-the-bridge.md):
  python bridge.py --api-key <key>                  # server only, port 8000, reachable on the LAN
  python bridge.py                                  # no key: only for a quick test on your own Wi-Fi
  python bridge.py --poll http://10.218.60.52/capture --every 60
  python bridge.py --usb 0 --every 30               # laptop / USB webcam
Model: models/best.pt next to this file (override with --weights or SMARTPHSET_WEIGHTS).
Logs:  bridge_log/ next to this file (override with --log or SMARTPHSET_LOG_DIR).

Endpoints:
  POST /telemetry          JSON {"device":"esp32-1","temp_c":27.1,"rh":88.5, ...optional fields}
  POST /image?camera=cam1  raw JPEG bytes in the body (Content-Type: image/jpeg)
  GET  /status             latest telemetry + latest verdict per camera, with age and stale flag
  GET  /latest.jpg?camera=cam1   last annotated image
  GET  /                   human status page (auto-refreshes) + upload box

Honest limits: demo model (public data, not field-validated). "no_detection", "camera_error" and
stale cameras mean "inspection unavailable", never "healthy". The bridge only logs climate; it does
not switch mist/fans -- the ESP32 does that locally so control survives a laptop or Wi-Fi failure.
Open the CSV logs as a copy (or read-only) while the bridge runs; Excel locks files it opens.
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import threading
import time
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

import cv2
import numpy as np
from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WEIGHTS = os.environ.get("SMARTPHSET_WEIGHTS") or os.path.join(HERE, "models", "best.pt")
DEFAULT_LOG = os.environ.get("SMARTPHSET_LOG_DIR") or os.path.join(HERE, "bridge_log")

TELEMETRY_COLS = ["time", "device", "temp_c", "rh", "co2_ppm", "mist_on", "fan_on", "water_ok", "fault", "extra"]
VISION_COLS = ["time", "camera", "verdict", "message", "n_contaminated", "n_healthy", "max_conf",
               "max_contaminated_conf", "width", "height", "ms", "image"]
ALARM = ("contamination_suspected", "camera_error", "no_detection", "STALE")

state = {"telemetry": {}, "vision": {}}  # latest per device / per camera
lock = threading.Lock()  # guards state and CSV writes
model_lock = threading.Lock()


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def safe_name(value, default):
    """Device/camera ids come from the network; keep them safe as file-name parts."""
    name = re.sub(r"[^A-Za-z0-9_-]", "_", str(value or ""))[:40]
    return name or default


def append_csv(path, cols, row):
    """Fixed columns per file; a locked or unwritable file is reported, never fatal."""
    try:
        new = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerow(row)
    except OSError as e:
        print(f"[{now()}] LOG WRITE FAILED ({os.path.basename(path)}): {e} -- is it open in Excel?")


def run_vision(jpeg_bytes, camera, args, model):
    """Decode -> predict -> save -> verdict dict. Never reports 'healthy' on a bad frame."""
    ts = now()
    img = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR) if jpeg_bytes else None
    if img is None:
        result = {"time": ts, "camera": camera, "verdict": "camera_error",
                  "message": "Image missing or unreadable -- inspection unavailable.",
                  "n_contaminated": 0, "n_healthy": 0, "max_conf": 0.0, "max_contaminated_conf": 0.0,
                  "width": 0, "height": 0, "ms": 0, "image": ""}
    else:
        t = time.time()
        with model_lock:
            res = model.predict(img, conf=args.conf, imgsz=args.imgsz, verbose=False)[0]
        ms = int((time.time() - t) * 1000)
        names = [res.names[int(c)].lower() for c in res.boxes.cls.tolist()]
        confs = res.boxes.conf.tolist()
        n_c = sum(1 for n in names if n.startswith("contam"))
        n_h = len(names) - n_c
        c_confs = [c for n, c in zip(names, confs) if n.startswith("contam")]
        if n_c:
            verdict, msg = "contamination_suspected", f"Possible mould on {camera}: check and isolate the bag."
        elif n_h:
            verdict, msg = "no_contamination_seen", "Bags visible, no contamination flagged."
        else:
            verdict, msg = "no_detection", "No bag recognised -- check camera aim, focus or light."
        stamp = ts.replace(":", "-")
        img_dir = os.path.join(args.log, "images")
        os.makedirs(img_dir, exist_ok=True)
        ann_path = os.path.join(img_dir, f"{stamp}_{camera}_ann.jpg")
        cv2.imwrite(os.path.join(img_dir, f"{stamp}_{camera}_raw.jpg"), img)
        cv2.imwrite(ann_path, res.plot())
        result = {"time": ts, "camera": camera, "verdict": verdict, "message": msg,
                  "n_contaminated": n_c, "n_healthy": n_h,
                  "max_conf": round(max(confs), 3) if confs else 0.0,
                  "max_contaminated_conf": round(max(c_confs), 3) if c_confs else 0.0,
                  "width": img.shape[1], "height": img.shape[0], "ms": ms, "image": ann_path,
                  "boxes": [{"label": n, "conf": round(c, 3), "xyxy": [round(v) for v in b]}
                            for n, c, b in zip(names, confs, res.boxes.xyxy.tolist())]}
    result["_t"] = time.time()
    with lock:
        state["vision"][camera] = result
        append_csv(os.path.join(args.log, "vision.csv"), VISION_COLS, result)
    print(f"[{ts}] {camera}: {result['verdict']} ({result['ms']} ms)")
    return {k: v for k, v in result.items() if k != "_t"}


def poller(args, model):
    """Pull a frame every N seconds from a snapshot URL or a USB camera. Never dies."""
    cam_name = safe_name(args.camera, "cam1")
    cap, fails = None, 0
    while True:
        data = None
        try:
            if args.usb is not None:
                if cap is None:
                    cap = cv2.VideoCapture(args.usb)
                ok, frame = cap.read()
                if ok:
                    data, fails = cv2.imencode(".jpg", frame)[1].tobytes(), 0
                else:
                    fails += 1
                    if fails >= 3:  # unplugged? release and reopen on the next round
                        cap.release()
                        cap, fails = None, 0
            else:
                with urllib.request.urlopen(args.poll, timeout=10) as r:
                    data = r.read()
        except Exception as e:  # camera offline is a reportable state, not a crash
            print(f"[{now()}] {cam_name}: fetch failed: {e}")
        try:
            run_vision(data, cam_name, args, model)
        except Exception:
            traceback.print_exc()
        time.sleep(args.every)


def snapshot(args):
    """Copy of state with age and a stale flag per camera/device."""
    with lock:
        snap = {"telemetry": {k: dict(v) for k, v in state["telemetry"].items()},
                "vision": {k: dict(v) for k, v in state["vision"].items()}}
    t = time.time()
    for group, limit in (("vision", args.stale), ("telemetry", 120)):
        for d in snap[group].values():
            age = int(t - d.pop("_t", t))
            d["age_s"] = age
            d["stale"] = age > limit
            if group == "vision" and d["stale"]:
                d["verdict"] = "STALE"
                d["message"] = f"No new image for {age} s -- inspection unavailable."
    return snap


PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>SmartPhset bridge</title>
<style>body{font-family:sans-serif;margin:16px;color:#123}h1{color:#004aad}
td,th{border:1px solid #ccc;padding:4px 8px}table{border-collapse:collapse;margin-bottom:16px}
.bad{color:#b00;font-weight:bold}img{max-width:100%;width:420px;margin-right:8px}
.box{border:1px solid #004aad;padding:10px;margin:12px 0;max-width:520px}</style>
<h1>SmartPhset bridge -- live status</h1><p>Updated {time}. Demo model, not field-validated.</p>
<div class="box"><b>Test the AI with a photo</b><br>
<input type="file" id="f" accept="image/*"> camera name <input id="c" value="phone" size="8">
<button onclick="send()">Check</button> <span id="r"></span></div>
<div id="live"><h2>Climate (from controller)</h2>{tele}<h2>Vision (per camera)</h2>{vis}</div>
<script>
async function send(){const f=document.getElementById('f').files[0];if(!f)return;
 document.getElementById('r').textContent='checking...';
 const k=new URLSearchParams(location.search).get('key')||'';
 const r=await fetch('/image?camera='+encodeURIComponent(document.getElementById('c').value)+'&key='+encodeURIComponent(k),
   {method:'POST',headers:{'Content-Type':'image/jpeg'},body:f});
 const j=await r.json();document.getElementById('r').textContent=j.verdict+' ('+j.ms+' ms)';
 setTimeout(()=>location.reload(),800);}
setInterval(()=>{if(!document.getElementById('f').files.length)location.reload()},5000);
</script>"""


def esc(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def table(rows):
    if not rows:
        return "<p>No data yet.</p>"
    keys = sorted({k for r in rows for k in r if k not in ("boxes", "image")})
    head = "".join(f"<th>{esc(k)}</th>" for k in keys)
    body = ""
    for r in rows:
        cells = ""
        for k in keys:
            v = r.get(k, "")
            cls = ' class="bad"' if str(v) in ALARM or (k == "stale" and v is True) else ""
            cells += f"<td{cls}>{esc(v)}</td>"
        body += f"<tr>{cells}</tr>"
    return f"<table><tr>{head}</tr>{body}</table>"


def make_handler(args, model):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, body, ctype="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, indent=1).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # keep the console readable
            pass

        def authorized(self, u):
            """With --api-key set, every request needs 'Authorization: Bearer <key>' or '?key=<key>'."""
            if not args.api_key:
                return True
            if self.headers.get("Authorization", "") == f"Bearer {args.api_key}":
                return True
            return parse_qs(u.query).get("key", [""])[0] == args.api_key

        def do_GET(self):
            u = urlparse(self.path)
            if not self.authorized(u):
                return self.send(401, {"error": "unauthorized"})
            q = parse_qs(u.query)
            snap = snapshot(args)
            if u.path == "/status":
                return self.send(200, snap)
            if u.path == "/latest.jpg":
                cam = safe_name(q.get("camera", ["cam1"])[0], "cam1")
                p = snap["vision"].get(cam, {}).get("image")
                if p and os.path.exists(p):
                    with open(p, "rb") as f:
                        return self.send(200, f.read(), "image/jpeg")
                return self.send(404, {"error": f"no image yet for {cam}"})
            if u.path == "/":
                vis = table(list(snap["vision"].values()))
                key = quote(q.get("key", [""])[0])
                vis += "".join(f'<img src="/latest.jpg?camera={c}&key={key}&t={time.time()}" alt="{c}">'
                               for c in snap["vision"])
                html = PAGE.replace("{time}", now()).replace("{tele}", table(list(snap["telemetry"].values())))
                return self.send(200, html.replace("{vis}", vis), "text/html; charset=utf-8")
            self.send(404, {"error": "unknown path"})

        def do_POST(self):
            try:
                u = urlparse(self.path)
                body = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
                if not self.authorized(u):
                    return self.send(401, {"error": "unauthorized"})
                if u.path == "/telemetry":
                    try:
                        d = json.loads(body)
                        d["temp_c"], d["rh"] = float(d["temp_c"]), float(d["rh"])
                    except Exception:
                        return self.send(400, {"ok": False, "error": "need JSON with numeric temp_c and rh"})
                    d["device"] = safe_name(d.get("device"), "esp32-1")
                    d["time"] = now()
                    d["extra"] = json.dumps({k: v for k, v in d.items() if k not in TELEMETRY_COLS})
                    with lock:
                        state["telemetry"][d["device"]] = dict(d, _t=time.time())
                        append_csv(os.path.join(args.log, f"telemetry_{d['device']}.csv"), TELEMETRY_COLS, d)
                    return self.send(200, {"ok": True, "time": d["time"]})
                if u.path == "/image":
                    cam = safe_name(parse_qs(u.query).get("camera", ["cam1"])[0], "cam1")
                    return self.send(200, run_vision(body, cam, args, model))
                self.send(404, {"error": "unknown path"})
            except Exception as e:
                traceback.print_exc()
                self.send(500, {"ok": False, "error": str(e)})

    return Handler


def main():
    ap = argparse.ArgumentParser(description="SmartPhset hardware bridge")
    ap.add_argument("--weights", default=DEFAULT_WEIGHTS)
    ap.add_argument("--log", default=DEFAULT_LOG, help="folder for CSV logs and saved images")
    ap.add_argument("--host", default="0.0.0.0", help="0.0.0.0 = reachable from other devices on the Wi-Fi")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--conf", type=float, default=0.4)
    ap.add_argument("--imgsz", type=int, default=416, help="model input size (trained at 416)")
    ap.add_argument("--poll", help="snapshot URL to pull, e.g. http://<esp32-cam-ip>/capture")
    ap.add_argument("--usb", type=int, help="USB camera index to pull from instead of a URL")
    ap.add_argument("--camera", default="cam1", help="name for the polled camera")
    ap.add_argument("--every", type=float, default=60, help="seconds between polled frames")
    ap.add_argument("--api-key", default=os.environ.get("BRIDGE_API_KEY", ""),
                    help="require this key on every request (header 'Authorization: Bearer <key>' or ?key=)")
    ap.add_argument("--stale", type=float, default=None,
                    help="seconds without a new image before a camera shows STALE (default 3x --every, min 180)")
    args = ap.parse_args()
    if args.stale is None:
        args.stale = max(180, 3 * args.every)

    os.makedirs(args.log, exist_ok=True)
    model = YOLO(args.weights)
    model.predict(np.zeros((args.imgsz, args.imgsz, 3), np.uint8), imgsz=args.imgsz, verbose=False)  # warm-up
    if args.poll or args.usb is not None:
        threading.Thread(target=poller, args=(args, model), daemon=True).start()
    srv = ThreadingHTTPServer((args.host, args.port), make_handler(args, model))
    print(f"SmartPhset bridge on http://{args.host}:{args.port}/  (logs: {args.log})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
